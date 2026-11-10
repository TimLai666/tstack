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

    def add(self, key, insight, *extra, cwd=None, kind="tool"):
        result = self.run_memory("add", "--type", kind, "--key", key, "--insight", insight,
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

    def test_fit_keeps_the_full_text_when_it_is_short_enough(self):
        self.add("uses-pnpm-workspace", "安裝一律用 corepack pnpm")
        self.add("temp-folder-blocks-exe", "暫存資料夾不能執行 exe", "--machine")
        self.assertEqual(self.run_memory("load", "--fit", "9000").stdout, self.run_memory("load").stdout)

    def test_fit_collapses_the_project_to_keys_before_touching_machine_facts(self):
        for i in range(12):
            self.add("long-project-rule-%02d" % i, "很長的專案經驗" * 120, kind="pitfall")
        self.add("temp-folder-blocks-exe", "暫存資料夾不能執行 exe", "--machine")
        shown = self.run_memory("load", "--fit", "3000").stdout
        self.assertLessEqual(len(shown), 3000)
        self.assertIn("keys only:", shown.split("\n", 1)[0])
        self.assertIn("# Machine memory — 1 fact(s)\n", shown)
        self.assertIn("long-project-rule-00", shown)
        self.assertIn("long-project-rule-11", shown)
        self.assertNotIn("很長的專案經驗很長的專案經驗", shown)
        self.assertIn("暫存資料夾不能執行 exe", shown)

    def test_fit_falls_back_to_machine_keys_and_never_exceeds_the_limit(self):
        for i in range(12):
            self.add("long-project-rule-%02d" % i, "很長的專案經驗" * 120, kind="pitfall")
        for i in range(12):
            self.add("machine-fact-number-%02d" % i, "機器事實" * 70, "--machine")
        for limit in (2500, 900, 300):
            shown = self.run_memory("load", "--fit", str(limit)).stdout
            self.assertLessEqual(len(shown), limit, limit)
            self.assertNotIn("機器事實機器事實", shown)
        self.assertIn("machine-fact-number-00", self.run_memory("load", "--fit", "2500").stdout)

    def test_load_layout_keeps_a_blank_line_between_sections_and_before_the_reminder(self):
        self.add("uses-pnpm-workspace", "安裝一律用 corepack pnpm", kind="pitfall")
        self.add("temp-folder-blocks-exe", "暫存資料夾不能執行 exe", "--machine")
        self.add("docker-needs-sudo", "docker 要加 sudo", "--host", "devbox")
        shown = self.run_memory("load").stdout
        self.assertRegex(shown, r"安裝一律用 corepack pnpm\n\n# Machine memory — 1 fact\(s\)\n- \*\*temp-folder-blocks-exe\*\*")
        self.assertRegex(shown, r"暫存資料夾不能執行 exe\n\n# Remote hosts with recorded facts: devbox \(1\)\n")
        self.assertIn("run `load --host <name>`.\n\n---\nBefore this session ends", shown)
        self.assertTrue(shown.endswith("no announcement is needed.\n"))
        alone = self.run_memory("load", cwd=self.second).stdout
        self.assertTrue(alone.startswith("NO_LEARNINGS ("))

    def test_fit_rejects_limits_too_small_to_carry_a_message(self):
        for bad in ("0", "-5", "199"):
            refused = self.run_memory("load", "--fit", bad)
            self.assertEqual(refused.returncode, 2, bad)
            self.assertIn("200", refused.stderr)

    def test_fit_trims_only_the_project_key_list_and_keeps_the_rest(self):
        for i in range(60):
            self.add("project-rule-with-a-long-descriptive-key-%02d" % i, "很長的專案經驗" * 60, kind="pitfall")
        for i in range(6):
            self.add("machine-fact-number-%02d" % i, "機器事實" * 70, "--machine")
        self.add("docker-needs-sudo", "docker 要加 sudo", "--host", "devbox")
        shown = self.run_memory("load", "--fit", "2600").stdout
        self.assertLessEqual(len(shown), 2600)
        self.assertIn("keys only:", shown.split("\n", 1)[0])
        self.assertIn("project-rule-with-a-long-descriptive-key-00", shown)
        self.assertNotIn("project-rule-with-a-long-descriptive-key-59", shown)
        self.assertRegex(shown, r"… and \d+ more; run `load` to list them")
        self.assertIn("machine-fact-number-05", shown)
        self.assertIn("devbox (1)", shown)
        self.assertIn("Before this session ends", shown)

    def test_fit_with_an_empty_project_keeps_the_no_learnings_line(self):
        for i in range(40):
            self.add("machine-fact-number-%02d" % i, "機器事實" * 70, "--machine")
        shown = self.run_memory("load", "--fit", "3000", cwd=self.second).stdout
        self.assertLessEqual(len(shown), 3000)
        self.assertTrue(shown.startswith("NO_LEARNINGS ("))
        self.assertIn("# Machine memory — 40 fact(s), keys only:", shown)
        self.assertIn("machine-fact-number-39", shown)

    def test_path_and_stats_follow_the_machine_flag(self):
        self.assertIn(os.path.join(".tstack", "machine", "learnings.jsonl"), self.run_memory("path", "--machine").stdout)
        self.assertIn(os.path.join(".tstack", "projects", "first-project"), self.run_memory("path").stdout)
        self.add("temp-folder-blocks-exe", "暫存資料夾不能執行 exe", "--machine")
        self.assertIn("1 live key(s)", self.run_memory("stats", "--machine").stdout)


class GlobalPreferences(unittest.TestCase):
    """What the user wants in every project lives in its own store, not in their instruction files."""

    setUp = MachineScope.setUp
    run_memory = MachineScope.run_memory
    add = MachineScope.add

    def test_global_preference_is_stored_apart_and_shown_in_every_project(self):
        saved = self.add("fix-small-visual-flaws", "看到明顯的小瑕疵就順手修，不用先問", "--global", kind="preference")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertTrue((self.home / ".tstack" / "global" / "learnings.jsonl").is_file())
        self.assertFalse((self.home / ".tstack" / "projects").exists())
        self.assertFalse((self.home / ".tstack" / "machine").exists())
        for project in (self.first, self.second):
            shown = self.run_memory("load", cwd=project).stdout
            self.assertIn("# Global memory — 1 preference(s)", shown)
            self.assertIn("看到明顯的小瑕疵就順手修", shown)

    def test_load_orders_project_then_global_then_machine(self):
        self.add("uses-pnpm-workspace", "安裝一律用 corepack pnpm", kind="pitfall")
        self.add("temp-folder-blocks-exe", "暫存資料夾不能執行 exe", "--machine")
        self.add("fix-small-visual-flaws", "看到明顯的小瑕疵就順手修", "--global", kind="preference")
        shown = self.run_memory("load").stdout
        order = [shown.index(mark) for mark in ("uses-pnpm-workspace", "# Global memory", "# Machine memory", "---\nBefore")]
        self.assertEqual(order, sorted(order))
        self.assertIn("--global", shown)  # the recording reminder says how to save one
        only = self.run_memory("load", "--global").stdout
        self.assertIn("fix-small-visual-flaws", only)
        self.assertNotIn("temp-folder-blocks-exe", only)
        self.assertNotIn("uses-pnpm-workspace", only)

    def test_global_cannot_be_combined_and_shares_the_length_limit(self):
        self.assertEqual(self.add("some-preference-rule", "x", "--global", "--machine").returncode, 2)
        self.assertEqual(self.add("some-preference-rule", "x", "--global", "--host", "devbox").returncode, 2)
        self.assertEqual(self.add("too-long-preference", "很長" * 200, "--global").returncode, 2)

    def test_search_stats_and_path_cover_the_global_store(self):
        self.add("fix-small-visual-flaws", "看到明顯的小瑕疵就順手修", "--global", kind="preference")
        self.assertIn("順手修", self.run_memory("search", "visual-flaws", cwd=self.second).stdout)
        self.assertIn("1 live key(s)", self.run_memory("stats", "--global").stdout)
        self.assertIn(os.path.join(".tstack", "global", "learnings.jsonl"), self.run_memory("path", "--global").stdout)

    def test_fit_reduces_global_and_machine_stores_to_keys_together(self):
        for i in range(12):
            self.add("long-project-rule-%02d" % i, "很長的專案經驗" * 120, kind="pitfall")
        for i in range(10):
            self.add("global-preference-%02d" % i, "個人偏好" * 70, "--global", kind="preference")
            self.add("machine-fact-number-%02d" % i, "機器事實" * 70, "--machine")
        shown = self.run_memory("load", "--fit", "2600").stdout
        self.assertLessEqual(len(shown), 2600)
        self.assertIn("# Global memory — 10 preference(s), keys only:", shown)
        self.assertIn("# Machine memory — 10 fact(s), keys only:", shown)
        self.assertIn("global-preference-09", shown)
        self.assertIn("machine-fact-number-09", shown)


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
