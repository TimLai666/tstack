"""Provider compatibility and instruction contracts without starting model CLIs."""
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dispatch_under_test", ROOT / "scripts/dispatch.py")
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)
POLICY = json.loads((ROOT / "scripts/policy.json").read_text())


class Contract(unittest.TestCase):
    def test_model_families_and_version_floors(self):
        cases = [
            ("implementation", 2, ["gpt-5.6-luna", "gpt-6-luna", "gpt-6.1-sol", "gpt-7.1-luna"], "gpt-7.1-luna"),
            ("classification", 2, ["haiku", "claude-haiku-4-5", "claude-haiku-5-5"], "claude-haiku-5-5"),
            ("frontend", 0, ["gpt-oss-120b-medium", "gemini-3.8-flash-high", "gemini-3.8-flash-medium"], "gemini-3.8-flash-medium"),
            ("review", 1, ["gpt-6.1-luna", "gpt-6-sol", "gpt-6.1-sol"], "gpt-6.1-sol"),
        ]
        for kind, level_index, models, expected in cases:
            with self.subTest(kind=kind):
                self.assertEqual(dispatch.select_model(POLICY["tasks"][kind]["levels"][level_index], models), expected)

    def test_external_cli_permission_and_effort_flags(self):
        prompt = "literal 'quotes' $(touch SHOULD_NOT_RUN) `echo no`\nnext line"
        cases = [
            ("implementation", 0, "opencode/big-pickle", ["--auto", "--agent", "build", "--print-logs", "ERROR"]),
            ("frontend", 0, "gemini-3.8-flash-medium", ["--mode", "accept-edits", "--dangerously-skip-permissions"]),
            ("classification", 0, "auto", ["--allow-all-tools", "--trust-folder"]),
            ("review", 1, "gpt-6-sol", ["--approve-for-me", "model_reasoning_effort=medium"]),
            ("implementation", 5, "claude-opus-5-5", ["--permission-mode", "auto", "--effort", "low"]),
        ]
        for kind, index, model, required in cases:
            with self.subTest(kind=kind, index=index):
                argv = dispatch.cli_argv(POLICY["tasks"][kind]["levels"][index], model, "/project", prompt)
                for value in required:
                    self.assertIn(value, argv)
                self.assertIn("-p=" + prompt if argv[0] == "agy" else prompt, argv)
                if argv[0] != "agy":
                    self.assertNotIn("--dangerously-skip-permissions", argv)

    def test_testing_and_readonly_prompt_requirements(self):
        request = dict(project_dir="/project", role="tester", prompt="Check the contract", allowed_files=[],
                       project_memory=[], verification=[], test_files=["tests.py"])
        readonly = dispatch.build_prompt(request, POLICY["tasks"]["exploration"], {})
        self.assertIn("不得修改任何專案檔案", readonly)
        self.assertIn("專案外的暫存目錄", readonly)
        testing = dispatch.build_prompt(dict(request, allowed_files=["tests.py"]), POLICY["tasks"]["testing"], {})
        self.assertIn("只寫測試，不寫實作", testing)
        self.assertNotIn("不得修改測試檔", testing)
        self.assertEqual(testing.splitlines()[0], dispatch.MARKER)
        self.assertIn("已確認原因", testing)
        self.assertIn("驗證證據", testing)

    def test_symlink_cannot_authorize_git_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            (project / ".git").mkdir()
            try:
                (project / "alias").symlink_to(project / ".git", target_is_directory=True)
            except OSError as exc:
                if os.name != "nt":
                    raise
                subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J",
                                str(project / "alias"), str(project / ".git")],
                               check=True, capture_output=True)
            with self.assertRaises(dispatch.DispatchError):
                dispatch.scoped_path("alias/config", project)

    @unittest.skipIf(os.name == "nt", "POSIX signals; Windows jobs covered by test_portability")
    def test_signal_permission_error_after_group_exit_is_verified(self):
        proc = mock.Mock(pid=12345)
        with mock.patch.object(dispatch.os, "killpg", side_effect=PermissionError(1, "Operation not permitted")), \
                mock.patch.object(dispatch, "group_live", return_value=False, create=True) as check:
            dispatch.terminate(proc)
            check.assert_called_with(12345)

    @unittest.skipIf(os.name == "nt", "POSIX signals; Windows jobs covered by test_portability")
    def test_signal_permission_error_with_live_group_is_not_ignored(self):
        proc = mock.Mock(pid=12345)
        with mock.patch.object(dispatch.os, "killpg", side_effect=PermissionError(1, "Operation not permitted")), \
                mock.patch.object(dispatch, "group_live", return_value=True, create=True):
            with self.assertRaises(dispatch.DispatchError):
                dispatch.terminate(proc)

    def test_unconfirmed_cleanup_stops_fallback_and_keeps_file_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            root = dispatch.state_directory(str(root / "state"), project)
            request = dict(project_dir=str(project), host="codex", task_type="classification", role="tester",
                           prompt="classify", allowed_files=["data.txt"], project_memory=[], verification=[])
            state = dict(dispatch_id="fixture", request=request, attempts=[], feedback=[], status="new")
            path = root / "fixture.json"
            paths = [str(project / "data.txt")]

            def cleanup_denied(*args):
                args[5].update(cleanup_pending=True, process_group=12345, child_pid=None)
                return dict(returncode=1, output="quota exceeded", error="", launch_error=False,
                            timeout=False, interrupted=False, cleanup_pending=True, cleanup_error="access denied")

            with mock.patch.object(dispatch, "snapshot", return_value="same"), \
                    mock.patch.object(dispatch, "execute", side_effect=cleanup_denied) as execute:
                result = dispatch.drive(root, path, state, POLICY["tasks"]["classification"], paths, 1, 1)
            self.assertEqual(result["status"], "awaiting_review")
            self.assertEqual(result["level"], 1)
            self.assertEqual(execute.call_count, 1)
            self.assertTrue(json.loads(path.read_text())["cleanup_pending"])
            next_state = dict(dispatch_id="other", request=request, status="new")
            with self.assertRaises(dispatch.DispatchError):
                dispatch.claim(root, root / "other.json", next_state,
                               POLICY["tasks"]["classification"]["levels"][0], paths, False, .01)


class NativeHandoffLeases(unittest.TestCase):
    """A handoff to the host's built-in subagent launches nothing the script can watch."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.target = str(self.root / "project" / "shared.txt")

    def lease(self, name, **fields):
        dispatch.atomic_write(self.root / (name + ".json"), dict(dispatch_id=name, **fields))

    def claim(self, tool, native, paths):
        state = dict(dispatch_id="mine", status="new")
        spec = dict(tool=tool, family="sol")
        dispatch.claim(self.root, self.root / "mine.json", state, spec, paths, native, .2)
        return state

    def test_unreported_handoffs_do_not_hold_slots_or_files(self):
        for i in range(3):
            self.lease(f"stale-{i}", status="native_required", current_tool="codex",
                       owner_pid=None, write_paths=[self.target])
        state = self.claim("codex", False, [self.target])
        self.assertEqual(state["status"], "running")

    def test_running_external_workers_still_hold_the_host_slots_before_handoff(self):
        for i in range(3):
            self.lease(f"live-{i}", status="running", current_tool="claude",
                       owner_pid=os.getpid(), write_paths=[])
        with self.assertRaises(dispatch.NotStarted):
            self.claim("claude", True, [])

    def test_running_external_writer_still_blocks_handoff_on_the_same_file(self):
        self.lease("writer", status="running", current_tool="copilot",
                   owner_pid=os.getpid(), write_paths=[self.target])
        with self.assertRaises(dispatch.NotStarted):
            self.claim("claude", True, [self.target])

    def test_handoff_records_no_file_lease(self):
        state = self.claim("claude", True, [self.target])
        self.assertEqual((state["status"], state["write_paths"]), ("native_required", []))
        saved = json.loads((self.root / "mine.json").read_text())
        self.assertEqual(saved["write_paths"], [])


if __name__ == "__main__":
    unittest.main()
