"""Failure and input boundaries exercised without a live model."""
import json
import os
import subprocess
from pathlib import Path
import unittest

import test_acceptance as helpers


class Safety(unittest.TestCase):
    setUp = helpers.Acceptance.setUp
    fake = helpers.Acceptance.fake
    request = helpers.Acceptance.request
    cli = helpers.Acceptance.cli
    dispatch = helpers.Acceptance.dispatch

    def test_unknown_error_is_handed_to_the_agent(self):
        self.fake("copilot", "print('unexpected internal failure',file=sys.stderr);sys.exit(17)")
        result = self.dispatch()
        self.assertEqual(result["status"], "cli_failed")
        self.assertIn("unexpected internal failure", result["attempts"][-1]["error"])
        self.assertEqual(result["level"], 1)
        self.assertEqual(len((self.root / "calls").read_text().splitlines()), 1)

    def test_timeout_requires_review(self):
        self.fake("copilot", "import time; print('started',flush=True); time.sleep(10)")
        result = self.cli("dispatch", "--request", "-", "--timeout", "0.1", "--state-dir", str(self.state), request=self.request())
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "awaiting_review")
        self.assertEqual(payload["level"], 1)
        self.assertTrue(payload["attempts"][-1]["timeout"])
        self.assertEqual(len(payload["attempts"]), 1)

    def test_ignored_file_write_stops_fallback(self):
        (self.project / ".gitignore").write_text("secret.cache\n")
        (self.project / "secret.cache").write_text("before")
        self.fake("copilot", "Path('secret.cache').write_text('partial');print('quota exceeded',file=sys.stderr);sys.exit(1)")
        result = self.dispatch()
        self.assertEqual(result["status"], "awaiting_review")
        self.assertTrue(result["attempts"][-1]["files_changed"])
        self.assertEqual(result["level"], 1)

    def test_unknown_model_probe_error_requires_review(self):
        path = self.bin / ("agy.py" if os.name == "nt" else "agy")
        path.write_text("#!/usr/bin/env python3\nimport sys\nprint('internal database corruption',file=sys.stderr)\nsys.exit(1)\n")
        result = self.dispatch(task_type="review", allowed_files=[])
        self.assertEqual(result["status"], "cli_failed")
        self.assertEqual(result["level"], 1)
        self.assertIn("internal database corruption", result["attempts"][-1]["model_probe"]["error"])

    def test_descendants_stopped_before_fallback(self):
        self.fake("copilot", "import subprocess;child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']);Path('../child.pid').write_text(str(child.pid));print('quota exceeded',file=sys.stderr);sys.exit(1)")
        result = self.dispatch()
        self.assertEqual(result["status"], "cli_failed")
        pid = int((self.root / "child.pid").read_text())
        if os.name == "nt":
            from test_portability import dispatch
            self.assertFalse(dispatch.alive(pid))
            return
        import subprocess
        try:
            state = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], text=True, capture_output=True)
            self.assertTrue(state.returncode != 0 or state.stdout.strip().startswith("Z"), state.stdout)
        finally:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass

    def test_changed_already_dirty_file_stops_fallback(self):
        (self.project / "labels.txt").write_text("before")
        self.fake("copilot", "Path('labels.txt').write_text('after');print('quota exceeded',file=sys.stderr);sys.exit(1)")
        result = self.dispatch()
        self.assertEqual(result["status"], "awaiting_review")
        self.assertEqual(result["level"], 1)

    def test_host_mismatch(self):
        self.env["CLAUDECODE"] = "1"
        result = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state), request=self.request())
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.root / "calls").exists())

    def test_forbidden_paths(self):
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.project / "link").symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            if os.name != "nt":
                raise
            subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(self.project / "link"), str(outside)],
                           check=True, capture_output=True)
        for path in ("../outside/x", "/tmp/x", "*.py", "link/x", ".git/config"):
            with self.subTest(path=path):
                result = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state), request=self.request(allowed_files=[path]))
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse((self.root / "calls").exists())

    def test_readonly_scope(self):
        result = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state), request=self.request(task_type="review", allowed_files=["labels.txt"]))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.root / "calls").exists())

    def test_memory_and_catalog_source_required(self):
        for extra in ({"project_memory": None}, {"project_memory": [{"lesson": "missing source"}]}, {"model_source": ""}):
            with self.subTest(extra=extra):
                result = self.cli("dispatch", "--request", "-", "--state-dir", str(self.state), request=self.request(**extra))
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse((self.root / "calls").exists())

    def test_no_resumption_without_outcome_or_evidence(self):
        result = self.dispatch()
        base = ("dispatch", "--dispatch-id", result["dispatch_id"], "--state-dir", str(self.state))
        before = (self.root / "calls").read_text()
        for extra in ((), ("--outcome", "dispatch-failed", "--level", "3"),
                      ("--outcome", "dispatch-failed", "--level", "1", "--failure-reason", "quota")):
            with self.subTest(extra=extra):
                invalid = self.cli(*(base + extra))
                self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual((self.root / "calls").read_text(), before)

    def test_declared_test_files_are_protected(self):
        result = self.dispatch(task_type="implementation", allowed_files=["src.py"], test_files=["test_src.py"])
        self.assertEqual(result["status"], "cli_failed")
        self.assertIn("test_src.py", result["prompt"])
        self.assertIn("Do not modify the test files", result["prompt"])

    def test_state_is_outside_project_and_private(self):
        self.dispatch()
        self.assertEqual(list(self.project.iterdir()), [self.project / ".git"])
        for path in self.state.rglob("*"):
            if path.is_file():
                if os.name == "nt":
                    from test_portability import dispatch
                    dispatch.windows.ensure_private(path)
                else:
                    self.assertEqual(path.stat().st_mode & 0o077, 0, str(path))

    def test_query_markdown_matches_shipped_table(self):
        result = self.cli("list-types", "--markdown")
        self.assertEqual(result.returncode, 0, result.stderr)
        source = (helpers.SCRIPT.parents[1] / "SKILL.md").read_text()
        table = source.split("<!-- DISPATCH_POLICY_START -->", 1)[1].split("<!-- DISPATCH_POLICY_END -->", 1)[0].strip()
        self.assertEqual(result.stdout.strip(), table)


if __name__ == "__main__":
    unittest.main()
