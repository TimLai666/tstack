"""Machine facts live beside the project stores and are visible from every project."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "memory.py"


class MachineScope(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.first = Path(tmp.name) / "first-project"
        self.second = Path(tmp.name) / "second-project"
        for folder in (self.home, self.first, self.second):
            folder.mkdir()
        self.machine_file = self.home / ".tstack" / "machine" / "learnings.jsonl"

    def run_memory(self, *args, cwd=None):
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd or self.first, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=30)

    def add(self, key, insight, *extra, cwd=None):
        result = self.run_memory("add", "--type", "tool", "--key", key, "--insight", insight,
                                 "--confidence", "9", *extra, cwd=cwd)
        return result

    def test_machine_fact_is_stored_apart_and_seen_from_every_project(self):
        saved = self.add("no-external-agent-clis", "這台沒裝 opencode 與 codex，派工直接用內建 subagent", "--machine")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertTrue(self.machine_file.is_file())
        self.assertFalse((self.home / ".tstack" / "projects").exists())

        for project in (self.first, self.second):
            shown = self.run_memory("load", cwd=project).stdout
            self.assertIn("# Machine memory — 1 fact(s)", shown)
            self.assertIn("這台沒裝 opencode 與 codex", shown)

    def test_load_shows_project_memory_first_then_machine_facts_with_their_date(self):
        self.add("uses-pnpm-workspace", "安裝一律用 corepack pnpm")
        self.add("temp-folder-blocks-exe", "端點防護會擋從暫存資料夾啟動的 exe，改放使用者資料目錄", "--machine")
        shown = self.run_memory("load").stdout
        self.assertLess(shown.index("uses-pnpm-workspace"), shown.index("# Machine memory"))
        self.assertRegex(shown, r"\*\*temp-folder-blocks-exe\*\* \(9/10, \d{4}-\d{2}-\d{2}\)")
        self.assertIn("--machine", shown)  # the recording reminder says how to save one

    def test_machine_facts_show_even_when_the_project_has_no_memory(self):
        self.add("temp-folder-blocks-exe", "暫存資料夾不能執行 exe", "--machine")
        shown = self.run_memory("load", cwd=self.second).stdout
        self.assertIn("NO_LEARNINGS", shown)
        self.assertIn("暫存資料夾不能執行 exe", shown)

    def test_json_and_export_stay_project_only_unless_machine_is_asked(self):
        self.add("uses-pnpm-workspace", "安裝一律用 corepack pnpm")
        self.add("temp-folder-blocks-exe", "暫存資料夾不能執行 exe", "--machine")
        project = json.loads(self.run_memory("load", "--json").stdout)
        self.assertEqual([e["key"] for e in project], ["uses-pnpm-workspace"])
        machine = json.loads(self.run_memory("load", "--machine", "--json").stdout)
        self.assertEqual([e["key"] for e in machine], ["temp-folder-blocks-exe"])
        self.assertNotIn("temp-folder-blocks-exe", self.run_memory("load", "--all").stdout)
        only = self.run_memory("load", "--machine").stdout
        self.assertIn("temp-folder-blocks-exe", only)
        self.assertNotIn("uses-pnpm-workspace", only)

    def test_long_machine_fact_is_refused(self):
        refused = self.add("too-long-fact", "很長" * 200, "--machine")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("300", refused.stderr)
        self.assertFalse(self.machine_file.exists())
        self.assertEqual(self.add("long-project-lesson", "很長" * 200).returncode, 0)

    def test_search_finds_machine_facts_from_any_project(self):
        self.add("temp-folder-blocks-exe", "暫存資料夾不能執行 exe", "--machine")
        found = self.run_memory("search", "temp-folder", cwd=self.second).stdout
        self.assertIn("暫存資料夾不能執行 exe", found)
        self.assertIn("Machine", found)

    def test_readding_a_key_replaces_the_machine_fact(self):
        self.add("no-external-agent-clis", "這台沒裝 opencode", "--machine")
        self.add("no-external-agent-clis", "這台已經裝了 opencode", "--machine")
        shown = self.run_memory("load", "--machine").stdout
        self.assertIn("這台已經裝了 opencode", shown)
        self.assertNotIn("這台沒裝 opencode", shown)

    def test_path_and_stats_follow_the_machine_flag(self):
        self.assertIn(os.path.join(".tstack", "machine", "learnings.jsonl"), self.run_memory("path", "--machine").stdout)
        self.assertIn(os.path.join(".tstack", "projects", "first-project"), self.run_memory("path").stdout)
        self.add("temp-folder-blocks-exe", "暫存資料夾不能執行 exe", "--machine")
        self.assertIn("1 live key(s)", self.run_memory("stats", "--machine").stdout)


class RemoteHosts(MachineScope):
    """Facts about a machine reached over SSH are kept on this machine, one store per host."""

    def host_file(self, name):
        return self.home / ".tstack" / "hosts" / name / "learnings.jsonl"

    def test_host_fact_has_its_own_store_and_is_listed_but_not_shown_by_default(self):
        saved = self.add("docker-needs-sudo", "devbox 上 docker 要加 sudo", "--host", "devbox")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertTrue(self.host_file("devbox").is_file())
        self.assertFalse(self.machine_file.exists())

        shown = self.run_memory("load", cwd=self.second).stdout
        self.assertIn("devbox (1)", shown)
        self.assertIn("load --host", shown)
        self.assertNotIn("docker 要加 sudo", shown)

        host = self.run_memory("load", "--host", "devbox").stdout
        self.assertIn("# Host memory: devbox — 1 fact(s)", host)
        self.assertIn("docker 要加 sudo", host)

    def test_host_names_are_normalised_and_unsafe_ones_refused(self):
        self.assertEqual(self.add("docker-needs-sudo", "docker 要加 sudo", "--host", "DevBox.local").returncode, 0)
        self.assertTrue(self.host_file("devbox.local").is_file())
        for bad in ("../outside", "a/b", "..", "", "white space"):
            refused = self.add("docker-needs-sudo", "x", "--host", bad)
            self.assertEqual(refused.returncode, 2, bad)
        self.assertEqual(sorted(p.name for p in (self.home / ".tstack" / "hosts").iterdir()), ["devbox.local"])

    def test_host_and_machine_cannot_be_combined(self):
        refused = self.add("docker-needs-sudo", "x", "--host", "devbox", "--machine")
        self.assertEqual(refused.returncode, 2)

    def test_host_facts_share_the_length_limit_and_have_their_own_search_stats_and_path(self):
        self.assertEqual(self.add("too-long-fact", "很長" * 200, "--host", "devbox").returncode, 2)
        self.add("docker-needs-sudo", "devbox 上 docker 要加 sudo", "--host", "devbox")
        self.assertIn("docker 要加 sudo", self.run_memory("search", "docker", "--host", "devbox").stdout)
        self.assertIn("NO_MATCHES", self.run_memory("search", "docker").stdout)
        self.assertIn("1 live key(s)", self.run_memory("stats", "--host", "devbox").stdout)
        self.assertIn(os.path.join(".tstack", "hosts", "devbox", "learnings.jsonl"),
                      self.run_memory("path", "--host", "devbox").stdout)


if __name__ == "__main__":
    unittest.main()
