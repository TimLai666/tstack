"""End-to-end acceptance through isolated local CLI doubles, never live models."""
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import tempfile
import unittest
import shutil


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dispatch.py"


class Acceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.state = self.root / "state"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], PYTHONUTF8="1")
        for key in ("CODEX_THREAD_ID", "CLAUDECODE", "ANTIGRAVITY_AGENT", "OPENCODE"):
            self.env.pop(key, None)
        self.env["HOME"] = str(self.root)
        self.env["CALL_LOG"] = str(self.root / "calls")
        for tool in ("opencode", "agy", "copilot", "codex", "claude"):
            self.fake(tool, "print('quota exceeded', file=sys.stderr); sys.exit(1)")

    def fake(self, tool, behavior):
        content = "#!/usr/bin/env python3\nimport os,sys,json\nfrom pathlib import Path\n"
        content += ("if sys.argv[1:3] == ['debug', 'models']:\n print(json.dumps({'models': ["
                    "{'slug': 'gpt-6.1-luna', 'visibility': 'list'}, {'slug': 'gpt-6.1-sol', 'visibility': 'list'}, "
                    "{'slug': 'gpt-7-luna', 'visibility': 'hide'}]})); sys.exit(0)\n")
        content += "if 'models' in sys.argv:\n print('opencode/big-pickle\\ngemini-3.8-flash-medium\\nclaude-opus-5-5'); sys.exit(0)\n"
        content += "with open(os.environ['CALL_LOG'],'a') as f: f.write(json.dumps(sys.argv)+'\\n')\n"
        content += behavior + "\n"
        p = self.bin / (tool + ".py" if os.name == "nt" else tool)
        p.write_text(content, encoding="utf-8")
        p.chmod(0o755)
        if os.name == "nt":
            if not shutil.which("node"):
                self.skipTest("Windows CLI doubles require Node.js for npm-shim coverage")
            js = self.bin / (tool + ".js")
            js.write_text("const cp=require('child_process');const r=cp.spawnSync(" +
                          json.dumps(sys.executable) + ",[" + json.dumps(str(p)) +
                          ",...process.argv.slice(2)],{stdio:'inherit'});process.exit(r.status ?? 127);", encoding="utf-8")
            header = "@ECHO off\nGOTO start\n:find_dp0\nSET dp0=%~dp0\nEXIT /b\n:start\nSETLOCAL\nCALL :find_dp0\n"
            node_block = ('IF EXIST "%dp0%\\node.exe" (\n  SET "_prog=%dp0%\\node.exe"\n) ELSE (\n'
                          '  SET "_prog=node"\n  SET PATHEXT=%PATHEXT:;.JS;=;%\n)\n\n'
                          'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%" ')
            (self.bin / (tool + ".cmd")).write_text(header + node_block + '"%dp0%\\' + tool + '.js" %*\n')

    def request(self, **extra):
        result = dict(host="codex", task_type="classification", project_dir=str(self.project),
                      role="Classify with evidence", prompt="Classify issue A; $(touch INJECTED) `echo x`\nkeep quotes: 'x'",
                      project_memory=[dict(condition="issue", lesson="Use facts", source="verified fixture")],
                      allowed_files=["labels.txt"], verification=["python3 -m unittest"],
                      models={"codex": ["gpt-6.1-luna", "gpt-6.1-sol"], "claude": ["claude-haiku-5-5", "claude-opus-5-5"]},
                      model_source="isolated test catalog")
        result.update(extra)
        return result

    def cli(self, *args, request=None, background=False):
        # Workflow tests read the final result directly; background behavior has its own tests.
        if args and args[0] == "dispatch" and not background:
            args = (args[0], "--foreground", *args[1:])
        # Allow slow interpreter starts on a busy host; each worker timeout is tested separately.
        proc = subprocess.Popen([sys.executable, str(SCRIPT), *args], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=self.env, text=True, encoding="utf-8", start_new_session=os.name != "nt")
        try:
            out, err = proc.communicate(json.dumps(request) if request is not None else None, timeout=120)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                proc.kill()
            else:
                os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    proc.kill()
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
            raise
        return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)

    def dispatch(self, **extra):
        result = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state), request=self.request(**extra))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_queries_have_no_execution_or_state(self):
        result = self.cli("list-types", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("classification", result.stdout)
        result = self.cli("list-levels", "--task-type", "classification", "--host", "codex", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("native", result.stdout.lower())
        self.assertFalse((self.root / "calls").exists())
        self.assertFalse(self.state.exists())

    def hand_off(self, result, *extra):
        resumed = self.cli("dispatch", "--dispatch-id", result["dispatch_id"], "--outcome", "dispatch-failed",
                           "--failure-reason", "agent read the CLI error", "--state-dir", str(self.state), *extra)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        return json.loads(resumed.stdout)

    def test_external_failure_to_native_with_prompt_and_lessons(self):
        failed = self.dispatch()
        self.assertEqual((failed["status"], failed["level"], failed["tool"]), ("cli_failed", 1, "copilot"))
        self.assertIn("quota exceeded", failed["attempts"][-1]["error"])
        self.assertIn("dispatch-failed", failed["instruction"])
        result = self.hand_off(failed, "--level", "2")
        self.assertEqual(result["status"], "native_required")
        self.assertEqual(result["level"], 2)
        self.assertEqual(result["tool"], "codex")
        self.assertEqual(result["model"], "gpt-6.1-luna")
        self.assertIn(self.request()["prompt"], result["prompt"])
        self.assertIn("verified fixture", result["prompt"])
        self.assertIn("教訓", result["prompt"])
        self.assertIn("證據", result["prompt"])
        self.assertIn("project-memory", result["memory_reminder"])
        self.assertNotIn("尚未保存", result["memory_reminder"])
        self.assertFalse((self.project / "INJECTED").exists())
        self.assertEqual(len((self.root / "calls").read_text().splitlines()), 1)

    def test_task_local_level_error_before_execution(self):
        result = self.cli("dispatch", "--request", "-", "--level", "5", "--state-dir", str(self.state), request=self.request())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("此任務類型只有 3 檔", result.stderr + result.stdout)
        self.assertFalse((self.root / "calls").exists())

    def test_cannot_start_with_valid_but_skipped_level(self):
        result = self.cli("dispatch", "--request", "-", "--level", "2", "--state-dir", str(self.state), request=self.request())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("第 1", result.stderr + result.stdout)
        self.assertFalse((self.root / "calls").exists())

    def test_success_is_review_not_auto_accepted(self):
        self.fake("copilot", "print('Classified. Lesson: fixture.')")
        result = self.dispatch()
        self.assertEqual(result["status"], "awaiting_review")
        self.assertEqual(result["level"], 1)
        self.assertIn("project-memory", result["memory_reminder"])

    def test_literal_prompt_survives_cli_wrapper(self):
        self.fake("copilot", "print('accepted')")
        prompt = '繁體中文 "quotes" & echo BAD | < > %PATH% !name! ^\nnext line \\ '
        result = self.dispatch(prompt=prompt)
        self.assertEqual(result["status"], "awaiting_review")
        calls = [json.loads(line) for line in (self.root / "calls").read_text().splitlines()]
        self.assertEqual(calls[-1][-1], result["prompt"])
        self.assertIn(prompt, calls[-1][-1])

    def test_partial_work_stops_fallback(self):
        self.fake("copilot", "Path('labels.txt').write_text('partial'); print('quota exceeded', file=sys.stderr); sys.exit(1)")
        result = self.dispatch()
        self.assertEqual(result["status"], "awaiting_review")
        self.assertEqual(result["level"], 1)
        self.assertEqual(len((self.root / "calls").read_text().splitlines()), 1)
        disguised = self.cli("dispatch", "--dispatch-id", result["dispatch_id"], "--outcome", "dispatch-failed",
                             "--failure-reason", "quota", "--state-dir", str(self.state))
        self.assertNotEqual(disguised.returncode, 0)
        self.assertIn("不能冒充未派出", disguised.stderr)

    def test_native_failure_resume_then_complete(self):
        result = self.hand_off(self.dispatch(), "--level", "2")
        self.assertEqual(result["status"], "native_required")
        args = ("dispatch", "--dispatch-id", result["dispatch_id"], "--level", "3",
                "--outcome", "dispatch-failed", "--failure-reason", "native tool quota exceeded",
                "--state-dir", str(self.state))
        self.fake("claude", "print('Classified using persisted task')")
        resumed = self.cli(*args)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        state = json.loads(resumed.stdout)
        self.assertEqual(state["status"], "awaiting_review")
        done = self.cli("dispatch", "--dispatch-id", result["dispatch_id"], "--outcome", "completed",
                        "--state-dir", str(self.state))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["status"], "completed")
        replay = self.cli(*args)
        self.assertNotEqual(replay.returncode, 0)


if __name__ == "__main__":
    unittest.main()
