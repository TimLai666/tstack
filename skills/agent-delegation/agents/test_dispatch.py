"""Focused dispatch workflow regressions using the local fake CLIs only."""
import json
import sys
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import time
import unittest

import test_acceptance as helpers


class DispatchRegressions(unittest.TestCase):
    setUp = helpers.Acceptance.setUp
    fake = helpers.Acceptance.fake
    request = helpers.Acceptance.request
    cli = helpers.Acceptance.cli
    dispatch = helpers.Acceptance.dispatch

    def hand_off(self, result, *extra):
        self.assertEqual(result["status"], "cli_failed", result.get("reason"))
        resumed = self.resume(result["dispatch_id"], "--outcome", "dispatch-failed",
                              "--failure-reason", "agent read the CLI error", *extra)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        return json.loads(resumed.stdout)

    def resume(self, dispatch_id, *extra):
        return self.cli("dispatch", "--dispatch-id", dispatch_id,
                        "--state-dir", str(self.state), *extra)

    def install_counting_copilot(self):
        counter = self.root / "active-count"
        counter.write_text("0 0")
        self.env["ACTIVE_COUNT"] = str(counter)
        body = """import time,contextlib
p=Path(os.environ['ACTIVE_COUNT'])
@contextlib.contextmanager
def locked():
 with p.open('r+') as f:
  if os.name=='nt':
   import msvcrt
   while True:
    try: msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1); break
    except OSError: time.sleep(.01)
  else:
   import fcntl
   fcntl.flock(f,fcntl.LOCK_EX)
  try: yield f
  finally:
   if os.name=='nt': f.seek(0); msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
with locked() as f:
 a,m=map(int,f.read().split()); a+=1; m=max(m,a); f.seek(0); f.truncate(); f.write(f'{a} {m}'); f.flush()
time.sleep(.35)
with locked() as f:
 a,m=map(int,f.read().split()); f.seek(0); f.truncate(); f.write(f'{a-1} {m}'); f.flush()
print('completed')"""
        self.fake("copilot", body)
        return counter

    def parallel_classifications(self, files):
        def run(path):
            request = self.request(allowed_files=[path])
            for attempt in range(50):
                result = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state),
                                  request=request)
                if result.returncode == 0:
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload["status"], "awaiting_review", result.stdout)
                    self.assertEqual(payload["tool"], "copilot", result.stdout)
                    return payload
                if "Resource temporarily unavailable" not in result.stderr:
                    self.fail(f"dispatch failed without the recognized busy error: {result.stderr}")
                time.sleep(0.05 + attempt * 0.005)
            self.fail("dispatch remained busy after 50 bounded retries")
        with ThreadPoolExecutor(max_workers=len(files)) as pool:
            return list(pool.map(run, files))

    def claude_catalog(self):
        return {
            "models": {
                "codex": ["gpt-6.1-luna", "gpt-6.1-sol"],
                "claude": ["claude-haiku-5.5", "claude-sonnet-5.5", "claude-opus-5.5"],
            },
            "model_source": "isolated fake catalog",
        }

    def assert_task_calls_once(self, files, payloads):
        calls = [json.loads(line) for line in (self.root / "calls").read_text().splitlines()]
        self.assertEqual(len(calls), len(files))
        prompts = [argv[-1] for argv in calls]
        seen = Counter(path for path in set(files)
                       for prompt in prompts if path in prompt)
        self.assertEqual(seen, Counter(files))
        self.assertEqual(len({p["dispatch_id"] for p in payloads}), len(files))

    def test_coding_verification_retries_same_level_before_escalation(self):
        self.fake("copilot", "print('accepted report')")
        self.fake("codex", "print('accepted report')")
        started = self.hand_off(self.dispatch(host="agy", task_type="implementation",
                                              allowed_files=["src.py"]))
        self.assertEqual(started["status"], "awaiting_review")
        self.assertEqual(started["level"], 2)

        first = self.resume(started["dispatch_id"], "--outcome", "verification-failed",
                            "--level", "2", "--failure-reason", "assertion failed",
                            "--feedback", "handle empty input", "--partial-work-reviewed")
        self.assertEqual(first.returncode, 0, first.stderr)
        retried = json.loads(first.stdout)
        self.assertEqual(retried["status"], "awaiting_review")
        self.assertEqual(retried["level"], 2)
        self.assertIn("assertion failed", retried["prompt"])
        self.assertIn("handle empty input", retried["prompt"])

        second = self.resume(started["dispatch_id"], "--outcome", "verification-failed",
                             "--level", "3", "--failure-reason", "still fails",
                             "--partial-work-reviewed")
        self.assertEqual(second.returncode, 0, second.stderr)
        escalated = json.loads(second.stdout)
        self.assertEqual(escalated["level"], 3)
        self.assertEqual(escalated["status"], "awaiting_review")

    def test_native_dispatch_failure_cannot_skip_level(self):
        started = self.hand_off(self.dispatch())
        self.assertEqual(started["status"], "native_required")
        invalid = self.resume(started["dispatch_id"], "--outcome", "dispatch-failed",
                              "--level", "4", "--failure-reason", "native unavailable")
        self.assertNotEqual(invalid.returncode, 0)
        valid = self.resume(started["dispatch_id"], "--outcome", "dispatch-failed",
                             "--level", "3", "--failure-reason", "native unavailable")
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(json.loads(valid.stdout)["level"], 3)

    def test_opencode_zero_exit_json_error_is_failure_evidence(self):
        self.fake("opencode", "print(json.dumps({'type':'error','error':'quota exceeded'}))")
        result = self.dispatch(host="claude", task_type="chores", allowed_files=["notes.md"],
                               **self.claude_catalog())
        self.assertEqual((result["status"], result["level"], result["tool"]), ("cli_failed", 1, "opencode"))
        state = next(path for path in self.state.rglob("*.json")
                     if result["dispatch_id"] in path.read_text())
        saved = json.loads(state.read_text())
        attempts = saved.get("attempts", [])
        self.assertTrue(attempts)
        raw = json.dumps(attempts[0], ensure_ascii=False).lower()
        self.assertIn("quota", raw)
        self.assertIn("opencode", raw)

    def test_agy_claude_omits_effort_and_quota_reached_hands_off(self):
        self.fake("agy", "print('Error: Individual quota reached. Please upgrade your subscription.', file=sys.stderr)\n"
                         "print('AGY_ERROR: ' + json.dumps({'status':'RESOURCE_EXHAUSTED','error_code':429}), file=sys.stderr); sys.exit(3)")
        self.fake("codex", "print('accepted report')")
        result = self.hand_off(self.dispatch(host="claude", task_type="review", allowed_files=[]))
        self.assertEqual(result["status"], "awaiting_review")
        self.assertEqual((result["level"], result["tool"]), (2, "codex"))
        calls = [json.loads(line) for line in (self.root / "calls").read_text().splitlines()]
        agy = [argv for argv in calls if "--mode" in argv]
        self.assertEqual(len(agy), 1)
        self.assertNotIn("--effort", agy[0])

    def test_any_cli_error_text_is_handed_to_the_agent(self):
        self.fake("claude", "if 'claude-haiku-5-5' in sys.argv:\n"
                            " print('Some wording no script could predict', file=sys.stderr); sys.exit(1)\n"
                            "print('accepted report')")
        result = self.dispatch(host="agy", task_type="implementation", allowed_files=["src.py"],
                               models={"codex": ["gpt-6.1-luna"],
                                       "claude": ["claude-haiku-5-5", "claude-sonnet-5-5"]})
        for _ in range(4):
            result = self.hand_off(result)
        self.assertIn("Some wording no script could predict", result["attempts"][-2]["error"])
        self.assertEqual(result["status"], "awaiting_review")
        self.assertEqual((result["level"], result["model"]), (5, "claude-sonnet-5-5"))

    def test_codex_model_is_probed_without_caller_catalog(self):
        self.fake("codex", "print('accepted report')")
        result = self.hand_off(self.dispatch(host="claude", task_type="classification", allowed_files=[],
                                             models={"claude": ["claude-haiku-5-5"]}))
        self.assertEqual(result["status"], "awaiting_review", result)
        self.assertEqual((result["tool"], result["model"]), ("codex", "gpt-6.1-luna"))

    def test_exhausted_is_terminal_and_does_not_relaunch(self):
        started = self.hand_off(self.hand_off(self.dispatch(host="claude", task_type="classification",
                                                            **self.claude_catalog())))
        self.assertEqual(started["status"], "native_required")
        next_stage = self.resume(started["dispatch_id"], "--outcome", "dispatch-failed",
                                 "--failure-reason", "native unavailable")
        self.assertEqual(next_stage.returncode, 0, next_stage.stderr)
        terminal = json.loads(next_stage.stdout)
        self.assertEqual(terminal["status"], "exhausted")
        before = (self.root / "calls").read_text() if (self.root / "calls").exists() else ""
        again = self.resume(started["dispatch_id"], "--outcome", "dispatch-failed",
                            "--level", "3", "--failure-reason", "retry")
        self.assertNotEqual(again.returncode, 0)
        after = (self.root / "calls").read_text() if (self.root / "calls").exists() else ""
        self.assertEqual(before, after)

    def test_research_scope_requires_sandbox_and_keeps_writes_inside(self):
        no_sandbox = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state),
                              request=self.request(task_type="research", allowed_files=[],
                                                   sandbox_dir=None))
        self.assertNotEqual(no_sandbox.returncode, 0)
        sandbox = self.root / "research-sandbox"
        sandbox.mkdir()
        result = self.dispatch(task_type="research", allowed_files=[], sandbox_dir=str(sandbox))
        self.assertEqual(result["status"], "native_required")
        self.assertIn(str(sandbox), result["prompt"])

        project_scope = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state),
                                 request=self.request(task_type="research", allowed_files=["../project/labels.txt"],
                                                      sandbox_dir=str(sandbox)))
        self.assertNotEqual(project_scope.returncode, 0)
        self.assertFalse((self.root / "calls").exists())

    def test_resume_preserves_original_request_and_appends_feedback(self):
        started = self.hand_off(self.dispatch(**self.claude_catalog()))
        self.fake("claude", "print('accepted report')")
        changed = self.cli("dispatch", "--dispatch-id", started["dispatch_id"],
                           "--outcome", "dispatch-failed", "--level", "2",
                           "--failure-reason", "quota", "--feedback", "preserve this",
                           "--request", "-", "--state-dir", str(self.state),
                           request=self.request(prompt="replacement request"))
        # Resume has no request option in the contract; argparse must reject it instead of
        # accepting a replacement task payload.
        self.assertNotEqual(changed.returncode, 0)
        good = self.resume(started["dispatch_id"], "--outcome", "dispatch-failed",
                           "--level", "3", "--failure-reason", "quota",
                           "--feedback", "preserve this")
        self.assertEqual(good.returncode, 0, good.stderr)
        continued = json.loads(good.stdout)
        self.assertIn(self.request()["prompt"], continued["prompt"])
        self.assertNotIn("replacement request", continued["prompt"])
        self.assertIn("preserve this", continued["prompt"])

    OPENCODE_LOG = ('timestamp=2026-11-08T09:42:07.079Z level=ERROR run=f12e3a37 message="stream error" '
                    'providerID=opencode modelID=big-pickle session.id=ses_x small={small} agent={agent} mode=primary '
                    'error.error="AI_APICallError: {text}"')

    def opencode_logs_then_hangs(self, agent="build", small="false",
                                 text="Free usage limit reached. Subscribe to OpenCode Go to keep going: https://opencode.ai/go"):
        line = self.OPENCODE_LOG.format(agent=agent, small=small, text=text)
        self.fake("opencode", f"import time\nprint({line!r}, file=sys.stderr, flush=True)\ntime.sleep(60)")

    def test_opencode_silent_after_an_error_is_stopped_without_waiting_for_timeout(self):
        self.opencode_logs_then_hangs()
        began = time.monotonic()
        result = self.cli("dispatch", "--request", "-", "--timeout", "40", "--stall-timeout", "2",
                          "--state-dir", str(self.state),
                          request=self.request(task_type="implementation", allowed_files=["src.py"]))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(time.monotonic() - began, 20)
        payload = json.loads(result.stdout)
        self.assertEqual((payload["status"], payload["level"], payload["tool"]), ("cli_failed", 1, "opencode"))
        first = payload["attempts"][0]
        self.assertFalse(first["timeout"])
        self.assertIn("Free usage limit reached", first["fatal_error"])
        calls = [json.loads(line) for line in (self.root / "calls").read_text().splitlines()]
        self.assertIn("--print-logs", calls[0])

    def test_opencode_title_or_unrecognized_errors_do_not_stop_the_run(self):
        cases = [dict(agent="title", small="true"), dict(text="socket hang up")]
        for case in cases:
            with self.subTest(**case):
                line = self.OPENCODE_LOG.format(**{**dict(agent="build", small="false", text="x"), **case})
                self.fake("opencode", f"import time\nprint({line!r}, file=sys.stderr, flush=True)\n"
                                      "time.sleep(2.5)\nprint(json.dumps({'type':'text','part':{'text':'done'}}))")
                result = self.cli("dispatch", "--request", "-", "--stall-timeout", "5", "--state-dir", str(self.state),
                                  request=self.request(task_type="implementation", allowed_files=["src.py"]))
                payload = json.loads(result.stdout)
                self.assertEqual((payload["status"], payload["level"]), ("awaiting_review", 1))
                self.assertNotIn("fatal_error", payload["attempts"][0])

    def test_opencode_retrying_or_working_after_an_error_is_not_stopped(self):
        error = self.OPENCODE_LOG.format(agent="build", small="false", text="Provider rate limit exceeded")
        retrying = (f"import time\nprint({error!r}, file=sys.stderr, flush=True)\ntime.sleep(1.5)\n"
                    f"print({error!r}, file=sys.stderr, flush=True)\ntime.sleep(1.5)\n"
                    "print(json.dumps({'type':'text','part':{'text':'done'}}))")
        long_tool = (f"import time\nprint({error!r}, file=sys.stderr, flush=True)\ntime.sleep(0.5)\n"
                     "print(json.dumps({'type':'step_start'}), flush=True)\ntime.sleep(4)\n"
                     "print(json.dumps({'type':'text','part':{'text':'done'}}))")
        for name, body in (("retrying", retrying), ("long tool after recovery", long_tool)):
            with self.subTest(name):
                self.fake("opencode", body)
                result = self.cli("dispatch", "--request", "-", "--stall-timeout", "2.5", "--state-dir", str(self.state),
                                  request=self.request(task_type="implementation", allowed_files=["src.py"]))
                payload = json.loads(result.stdout)
                self.assertEqual((payload["status"], payload["level"]), ("awaiting_review", 1))
                self.assertNotIn("fatal_error", payload["attempts"][0])

    def remove_copilot(self):
        # Only the doubles and basic system tools, so no real copilot can stand in for the missing one.
        self.env["PATH"] = os.pathsep.join([str(self.bin), os.path.dirname(sys.executable)] +
                                           ([os.environ["SystemRoot"] + "\\System32"] if os.name == "nt" else ["/usr/bin", "/bin"]))
        (self.bin / ("copilot.py" if os.name == "nt" else "copilot")).unlink()
        if os.name == "nt":
            for suffix in (".js", ".cmd"):
                (self.bin / ("copilot" + suffix)).unlink()

    def confirm_not_installed(self, result, *extra):
        return self.cli("dispatch", "--dispatch-id", result["dispatch_id"], "--state-dir", str(self.state),
                        "--outcome", "dispatch-failed", "--not-installed",
                        "--failure-reason", "which copilot: not found; npm ls -g: absent", *extra)

    def test_missing_cli_is_handed_to_the_agent(self):
        self.remove_copilot()
        result = self.dispatch()
        self.assertEqual((result["status"], result["level"]), ("cli_failed", 1))
        self.assertTrue(result["attempts"][0]["launch_error"])

    def test_confirmed_missing_cli_is_skipped_by_later_dispatches(self):
        self.remove_copilot()
        handed = self.confirm_not_installed(self.dispatch())
        self.assertEqual(handed.returncode, 0, handed.stderr)
        self.assertEqual(json.loads(handed.stdout)["level"], 2)

        later = self.dispatch()
        self.assertEqual((later["status"], later["level"]), ("native_required", 2))
        skipped = later["attempts"][0]
        self.assertEqual((skipped["tool"], skipped["skipped"]), ("copilot", "not_installed"))
        self.assertIn("npm ls -g", skipped["evidence"])
        self.assertTrue(skipped["verified_at"])

    def test_missing_cli_record_is_dropped_when_the_command_appears(self):
        self.remove_copilot()
        self.confirm_not_installed(self.dispatch())
        self.fake("copilot", "print('quota exceeded', file=sys.stderr); sys.exit(1)")
        later = self.dispatch()
        self.assertEqual((later["status"], later["level"]), ("cli_failed", 1))
        self.assertFalse(later["attempts"][0]["launch_error"])

    def test_missing_cli_record_does_not_apply_under_another_path(self):
        self.remove_copilot()
        self.confirm_not_installed(self.dispatch())
        extra = self.root / "other-bin"
        extra.mkdir()
        self.env["PATH"] += os.pathsep + str(extra)
        later = self.dispatch()
        self.assertEqual((later["status"], later["level"]), ("cli_failed", 1))
        self.assertTrue(later["attempts"][0]["launch_error"])

    def test_missing_cli_record_expires(self):
        self.remove_copilot()
        self.confirm_not_installed(self.dispatch())
        cache = self.state / "not-installed.cache"
        data = json.loads(cache.read_text(encoding="utf-8"))
        data["copilot"]["verified_at"] -= 8 * 86400
        cache.write_text(json.dumps(data), encoding="utf-8")
        later = self.dispatch()
        self.assertEqual((later["status"], later["level"]), ("cli_failed", 1))

    def test_not_installed_needs_a_launch_failure(self):
        failed = self.dispatch()
        self.assertEqual(failed["status"], "cli_failed")
        refused = self.confirm_not_installed(failed)
        self.assertEqual(refused.returncode, 2)
        self.assertFalse((self.state / "not-installed.cache").exists())

    def test_cli_failure_resumes_only_to_the_next_level(self):
        failed = self.dispatch()
        for level in ("1", "3"):
            with self.subTest(level=level):
                rejected = self.resume(failed["dispatch_id"], "--outcome", "dispatch-failed", "--level", level,
                                       "--failure-reason", "quota")
                self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(self.hand_off(failed)["level"], 2)

    def test_unreported_handoffs_do_not_block_a_new_dispatch(self):
        helpers_module = __import__("test_portability").dispatch
        self.state.mkdir(mode=0o700)
        for i in range(3):
            helpers_module.atomic_write(self.state / f"0000000{i}-0000-4000-8000-000000000000.json", dict(
                dispatch_id=f"0000000{i}-0000-4000-8000-000000000000", status="native_required",
                current_tool="codex", owner_pid=None, write_paths=[str(self.project / "labels.txt")]))
        result = self.cli("dispatch", "--request", "-", "--timeout", "5", "--state-dir", str(self.state),
                          request=self.request())
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual((payload["status"], payload["level"], payload["tool"]), ("cli_failed", 1, "copilot"))
        self.assertEqual(self.hand_off(payload)["status"], "native_required")

    def test_same_file_dispatches_do_not_run_concurrently(self):
        counter = self.install_counting_copilot()
        payloads = self.parallel_classifications(["shared.txt", "shared.txt"])
        active, maximum = map(int, counter.read_text().split())
        self.assertEqual(active, 0)
        self.assertEqual(maximum, 1)
        self.assertEqual(len(payloads), 2)
        self.assert_task_calls_once(["shared.txt", "shared.txt"], payloads)

    def test_each_external_cli_is_limited_to_three_live_slots(self):
        counter = self.install_counting_copilot()
        payloads = self.parallel_classifications(["a.txt", "b.txt", "c.txt", "d.txt"])
        active, maximum = map(int, counter.read_text().split())
        self.assertEqual(active, 0)
        self.assertLessEqual(maximum, 3)
        self.assertEqual(len(payloads), 4)
        self.assert_task_calls_once(["a.txt", "b.txt", "c.txt", "d.txt"], payloads)


if __name__ == "__main__":
    unittest.main()
