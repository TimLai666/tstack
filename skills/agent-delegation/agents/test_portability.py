"""Real platform primitives; no installed model CLIs or paid calls."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("portable_dispatch", SCRIPTS / "dispatch.py")
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


class Portability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.state = dispatch.state_directory(str(self.root / "state"), self.project)

    def execute(self, code, timeout=10):
        state = {}
        result = dispatch.execute([sys.executable, "-c", code], str(self.project),
                                  self.state, "worker", timeout, state, self.state / "task.json")
        return result

    def test_help_and_queries(self):
        for args in ([], ["--help"], ["list-types", "--json"],
                     ["list-levels", "--task-type", "classification", "--host", "codex", "--json"]):
            result = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "dispatch.py"), *args],
                                    capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_lock_excludes_other_process_and_releases(self):
        lock = self.state / "shared.lock"
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import dispatch; "
                "from pathlib import Path\n"
                "with dispatch.lock_file(Path(sys.argv[2]), False): print('acquired')")
        def attempt():
            return subprocess.run([sys.executable, "-c", code, str(SCRIPTS), str(lock)],
                                  capture_output=True, timeout=10)
        with dispatch.lock_file(lock):
            self.assertNotEqual(attempt().returncode, 0)
        self.assertEqual(attempt().returncode, 0)

    def test_alive_never_terminates_a_process(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            self.assertTrue(dispatch.alive(proc.pid))
            time.sleep(.1)
            self.assertIsNone(proc.poll())
        finally:
            proc.kill()
            proc.wait()
        self.assertFalse(dispatch.alive(proc.pid))

    def test_success_preserves_unicode_and_literal_arguments(self):
        value = '繁體中文 "quotes" & echo BAD | %PATH% !x!\nsecond line'
        result = self.execute("import json; print(json.dumps(" + repr(value) + "))")
        self.assertEqual(result["returncode"], 0, result)
        self.assertEqual(json.loads(result["output"]), value)
        self.assertFalse(result["cleanup_pending"], result)

    def test_timeout_cleans_entire_tree(self):
        marker = self.root / "child.pid"
        code = ("import subprocess,sys,time; from pathlib import Path; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "Path(" + repr(str(marker)) + ").write_text(str(p.pid)); time.sleep(60)")
        result = self.execute(code, timeout=2)
        self.assertTrue(result["timeout"], result)
        self.assertFalse(result["cleanup_pending"], result)
        self.assertTrue(marker.exists(), result)
        pid = int(marker.read_text())
        if os.name == "nt":
            self.assertFalse(dispatch.alive(pid))
        else:
            status = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
            self.assertTrue(status.returncode or status.stdout.strip().startswith("Z"))

    def test_parent_exit_also_cleans_descendants(self):
        marker = self.root / "orphan.pid"
        code = ("import subprocess,sys; from pathlib import Path; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "Path(" + repr(str(marker)) + ").write_text(str(p.pid))")
        result = self.execute(code)
        self.assertFalse(result["cleanup_pending"], result)
        pid = int(marker.read_text())
        if os.name == "nt":
            self.assertFalse(dispatch.alive(pid))
        else:
            status = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
            self.assertTrue(status.returncode or status.stdout.strip().startswith("Z"))

    @unittest.skipUnless(os.name == "nt", "Windows ACL")
    def test_public_directory_and_file_are_rejected(self):
        for path in (self.root / "public", self.state / "public.json"):
            if path.suffix:
                path.write_text("{}")
            else:
                path.mkdir()
            subprocess.run(["icacls", str(path), "/grant", "*S-1-1-0:R"],
                           check=True, capture_output=True)
            with self.assertRaises(OSError):
                dispatch.windows.ensure_private(path)

    @unittest.skipUnless(os.name == "nt", "Windows jobs")
    def test_assignment_failure_does_not_start_worker(self):
        marker = self.root / "should-not-exist"
        with mock.patch.object(dispatch.windows, "assign_job", return_value=False):
            result = self.execute("from pathlib import Path; Path(" + repr(str(marker)) + ").touch()")
        self.assertFalse(marker.exists())
        self.assertNotEqual(result["returncode"], 0)

    @unittest.skipUnless(os.name == "nt", "Windows jobs")
    def test_dispatcher_crash_kills_worker_tree(self):
        marker = self.root / "worker.pid"
        statefile = self.state / "crash.json"
        worker = ("import os,time; from pathlib import Path; Path(" + repr(str(marker)) +
                  ").write_text(str(os.getpid())); time.sleep(60)")
        code = ("import sys; sys.path.insert(0,sys.argv[1]); import dispatch; from pathlib import Path; "
                "dispatch.execute([sys.executable,'-c',sys.argv[2]],sys.argv[3],Path(sys.argv[4]),"
                "'crash',60,{},Path(sys.argv[5]))")
        proc = subprocess.Popen([sys.executable, "-c", code, str(SCRIPTS), worker,
                                 str(self.project), str(self.state), str(statefile)])
        try:
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertTrue(marker.exists())
            saved = json.loads(statefile.read_text())
            self.assertTrue(saved["cleanup_pending"])
            pid = int(marker.read_text())
            proc.kill()
            proc.wait()
            deadline = time.monotonic() + 5
            while dispatch.alive(pid) and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertFalse(dispatch.alive(pid))
            self.assertFalse(dispatch.group_live(saved["process_group"]))
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    @unittest.skipUnless(os.name == "nt", "Windows CLI wrappers")
    def test_unknown_batch_is_not_executed(self):
        batch = self.root / "custom.cmd"
        marker = self.root / "injected"
        batch.write_text('@echo off\necho x > "' + str(marker) + '"\n')
        state = {}
        result = dispatch.execute([str(batch)], str(self.project), self.state, "batch", 10,
                                  state, self.state / "batch.json")
        self.assertFalse(result["launch_error"], result)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == "nt", "Windows junctions")
    def test_state_directory_junction_is_rejected(self):
        junction = self.root / "junction"
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(self.state)],
                       check=True, capture_output=True)
        with self.assertRaises(OSError):
            dispatch.state_directory(str(junction), self.project)

    @unittest.skipUnless(os.name == "nt", "Windows path resolution")
    def test_junction_cannot_authorize_git_metadata(self):
        metadata = self.project / ".git"
        metadata.mkdir()
        junction = self.project / "alias"
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(metadata)],
                       check=True, capture_output=True)
        with self.assertRaises(dispatch.DispatchError):
            dispatch.scoped_path("alias/config", self.project)


if __name__ == "__main__":
    unittest.main()
