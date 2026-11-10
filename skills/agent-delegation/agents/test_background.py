"""Background dispatch: detached supervision, status, cancel and recovery."""
import json
import os
from pathlib import Path
import signal
import sys
import time
import unittest

import test_acceptance as helpers
from test_portability import dispatch as module


def wait_until(check, limit=20):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("condition not met within %s seconds" % limit)


class Background(unittest.TestCase):
    setUp = helpers.Acceptance.setUp
    fake = helpers.Acceptance.fake
    request = helpers.Acceptance.request
    cli = helpers.Acceptance.cli

    def tearDown(self):
        # Never leave a detached supervisor behind a failed assertion.
        for path in self.state.glob("*.json") if self.state.exists() else []:
            with_state = json.loads(path.read_text())
            if with_state.get("status") in ("starting", "new", "running"):
                self.cli("cancel", "--dispatch-id", with_state["dispatch_id"], "--state-dir", str(self.state))

    def start(self, *extra, **request):
        began = time.monotonic()
        result = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state), *extra,
                          request=self.request(**request), background=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        payload["_elapsed"] = time.monotonic() - began
        return payload

    def status(self, dispatch_id, wait=0):
        result = self.cli("status", "--dispatch-id", dispatch_id, "--state-dir", str(self.state), "--wait", str(wait))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def cancel(self, dispatch_id):
        result = self.cli("cancel", "--dispatch-id", dispatch_id, "--state-dir", str(self.state))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def resume(self, dispatch_id, *extra, background=True):
        return self.cli("dispatch", "--dispatch-id", dispatch_id, "--state-dir", str(self.state), *extra,
                        background=background)

    def test_dispatch_returns_before_worker_and_status_returns_final_result(self):
        self.fake("copilot", "import time; time.sleep(4); print('classified')")
        started = self.start()
        self.assertEqual(started["status"], "started")
        self.assertLess(started["_elapsed"], 3.5, "dispatch must not wait for the worker or hold caller pipes")
        self.assertIn("status", started["instruction"])
        final = self.status(started["dispatch_id"], wait=30)
        self.assertEqual(final["status"], "awaiting_review")
        self.assertEqual((final["level"], final["tool"]), (1, "copilot"))
        self.assertFalse(final["attempts"][-1]["timeout"])

    def test_status_without_wait_reports_progress(self):
        self.fake("copilot", "import time; print('working', flush=True); time.sleep(30)")
        started = self.start()
        running = wait_until(lambda: (lambda s: s if s.get("phase") == "executing" and s["runtime"]["stdout_bytes"] else None)(
            self.status(started["dispatch_id"])))
        self.assertEqual(running["status"], "running")
        self.assertEqual(running["tool"], "copilot")
        self.assertGreaterEqual(running["runtime"]["elapsed"], 0)
        self.assertIn("stdout_age", running["runtime"])

    def test_cancel_stops_worker_tree_and_requires_review(self):
        pid_file = self.root / "child.pid"
        self.fake("copilot", "import subprocess,time\nchild=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])\n"
                             f"Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(120)")
        started = self.start()
        wait_until(pid_file.exists)
        stopped = self.cancel(started["dispatch_id"])
        self.assertEqual(stopped["status"], "awaiting_review")
        self.assertTrue(stopped["attempts"][-1]["interrupted"])
        self.assertFalse(stopped["attempts"][-1].get("cleanup_pending"))
        wait_until(lambda: not module.alive(int(pid_file.read_text())), 10)
        again = self.cancel(started["dispatch_id"])
        self.assertEqual(again["status"], "awaiting_review")

    def test_resume_is_rejected_while_background_run_is_active(self):
        self.fake("copilot", "import time; time.sleep(30)")
        started = self.start()
        rejected = self.resume(started["dispatch_id"], "--outcome", "verification-failed",
                               "--failure-reason", "x", "--partial-work-reviewed")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("執行", rejected.stderr)

    def test_stale_stop_request_does_not_cancel_next_run(self):
        self.fake("opencode", "import time; time.sleep(30)")
        started = self.start(task_type="implementation", host="agy", allowed_files=["src.py"])
        wait_until(lambda: self.status(started["dispatch_id"]).get("phase") == "executing")
        self.assertTrue(self.cancel(started["dispatch_id"])["attempts"][-1]["interrupted"])
        self.fake("opencode", "print('second run')")
        resumed = self.resume(started["dispatch_id"], "--outcome", "verification-failed",
                              "--failure-reason", "cancelled run reviewed", "--partial-work-reviewed")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(resumed.stdout)["status"], "started")
        final = self.status(started["dispatch_id"], wait=30)
        self.assertEqual(final["status"], "awaiting_review")
        self.assertFalse(final["attempts"][-1]["interrupted"])

    @unittest.skipIf(os.name == "nt", "Windows job objects stop the worker tree with the supervisor")
    def test_lost_supervisor_is_reported_and_cancel_cleans_orphaned_worker(self):
        pid_file = self.root / "child.pid"
        self.fake("copilot", "import subprocess,time\nchild=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])\n"
                             f"Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(120)")
        started = self.start()
        wait_until(pid_file.exists)
        os.kill(started["supervisor_pid"], signal.SIGKILL)
        wait_until(lambda: not module.alive(started["supervisor_pid"]) or None, 10)
        lost = self.status(started["dispatch_id"])
        self.assertEqual(lost["status"], "awaiting_review")
        self.assertTrue(lost["attempts"][-1]["supervisor_lost"])
        self.assertIn("cancel", lost["reason"])
        cleaned = self.cancel(started["dispatch_id"])
        self.assertEqual(cleaned["status"], "awaiting_review")
        self.assertFalse(json.loads(Path(cleaned["state_path"]).read_text())["cleanup_pending"])
        wait_until(lambda: not module.alive(int(pid_file.read_text())), 10)

    def test_slot_wait_timeout_is_not_started_and_retries_same_level(self):
        self.fake("copilot", "import time; time.sleep(30)")
        holder = self.start(allowed_files=["shared.txt"])
        wait_until(lambda: self.status(holder["dispatch_id"]).get("phase") == "executing")
        blocked = self.start("--timeout", "0.5", allowed_files=["shared.txt"])
        waiting = self.status(blocked["dispatch_id"], wait=20)
        self.assertEqual(waiting["status"], "not_started")
        self.assertEqual(waiting["level"], 1)
        self.assertEqual(waiting["attempts"], [])
        self.cancel(holder["dispatch_id"])
        self.fake("copilot", "print('done')")
        retried = self.resume(blocked["dispatch_id"], "--outcome", "dispatch-failed", "--level", "1",
                              "--failure-reason", "slot wait timed out")
        self.assertEqual(retried.returncode, 0, retried.stderr)
        final = self.status(blocked["dispatch_id"], wait=30)
        self.assertEqual((final["status"], final["level"]), ("awaiting_review", 1))

    def test_status_keeps_waiting_while_the_next_level_is_queued(self):
        self.fake("codex", "import time\nif 'HOLD' in sys.argv[-1]: time.sleep(30)\nprint('accepted report')")
        holders = []
        for i in range(3):
            sandbox = self.root / f"sandbox-{i}"
            sandbox.mkdir()
            holders.append(self.start(host="claude", task_type="research", allowed_files=[],
                                      sandbox_dir=str(sandbox), prompt=f"HOLD {i}"))
        for holder in holders:
            wait_until(lambda: self.status(holder["dispatch_id"]).get("phase") == "executing")
        moving = self.start(host="claude", task_type="classification", allowed_files=[],
                            models={"claude": ["claude-haiku-5-5"]}, model_source="isolated test catalog")
        self.assertEqual(self.status(moving["dispatch_id"], wait=20)["status"], "cli_failed")
        resumed = self.resume(moving["dispatch_id"], "--outcome", "dispatch-failed", "--failure-reason", "copilot quota")
        self.assertEqual(json.loads(resumed.stdout)["status"], "started", resumed.stderr)
        waiting = wait_until(lambda: (lambda s: s if s["level"] == 2 else None)(self.status(moving["dispatch_id"])))
        self.assertEqual((waiting["status"], waiting["phase"], waiting["tool"]), ("new", "queued", "codex"))
        self.assertEqual(self.status(moving["dispatch_id"], wait=1)["status"], "new")
        stopped = self.cancel(moving["dispatch_id"])
        self.assertEqual((stopped["status"], stopped["level"]), ("not_started", 2))

    def test_cancel_while_queued_is_not_started(self):
        self.fake("copilot", "import time; time.sleep(30)")
        holder = self.start(allowed_files=["shared.txt"])
        wait_until(lambda: self.status(holder["dispatch_id"]).get("phase") == "executing")
        queued = self.start(allowed_files=["shared.txt"])
        wait_until(lambda: self.status(queued["dispatch_id"]).get("phase") == "queued")
        stopped = self.cancel(queued["dispatch_id"])
        self.assertEqual(stopped["status"], "not_started")
        self.assertEqual(stopped["attempts"], [])
        self.assertEqual(self.status(holder["dispatch_id"])["status"], "running")

    def test_native_first_level_returns_synchronously(self):
        result = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state),
                          request=self.request(host="copilot"), background=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "native_required")

    def test_default_timeout_is_one_execution_of_thirty_minutes(self):
        policy = json.loads(module.POLICY_PATH.read_text(encoding="utf-8"))
        parsed = module.parser(policy).parse_args(["dispatch", "--request", "task.json"])
        self.assertEqual(parsed.timeout, 1800)
        self.assertFalse(parsed.foreground)
        self.assertEqual(parsed.stall_timeout, 180)


if __name__ == "__main__":
    unittest.main()
