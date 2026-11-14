"""A lesson promoted into the repository leaves the default view but never the file."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "memory.py"


class Promote(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.project = Path(tmp.name) / "project"
        for folder in (self.home, self.project):
            folder.mkdir()

    def run_memory(self, *args):
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.project, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=30)

    def add(self, key, insight, kind="pitfall", *extra):
        result = self.run_memory("add", "--type", kind, "--key", key, "--insight", insight,
                                 "--confidence", "9", *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def store_lines(self):
        path = Path(self.run_memory("path").stdout.strip())
        return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def test_promoted_entry_leaves_load_but_stays_in_the_file_and_in_search(self):
        self.add("run-migrations-before-tests", "tests fail on a cold db; run rake db:migrate first")
        self.add("node-18-only-here", "this machine has node 18, the project wants 20; nvm use 20")
        (self.project / "AGENTS.md").write_text("- Run `rake db:migrate` before the test suite.\n", encoding="utf-8")

        promoted = self.run_memory("promote", "--key", "run-migrations-before-tests", "--to", "AGENTS.md")
        self.assertEqual(promoted.returncode, 0, promoted.stderr)
        self.assertEqual(promoted.stdout.strip(), "PROMOTED run-migrations-before-tests -> AGENTS.md")
        self.assertEqual(promoted.stderr, "")

        shown = self.run_memory("load").stdout
        self.assertNotIn("run-migrations-before-tests", shown)
        self.assertIn("node-18-only-here", shown)
        self.assertIn("# Project memory — 1 learning(s)", shown)

        everything = self.run_memory("load", "--all").stdout
        self.assertIn("**run-migrations-before-tests** (9/10) — tests fail on a cold db", everything)
        self.assertIn("(promoted to AGENTS.md)", everything)

        found = self.run_memory("search", "cold db").stdout
        self.assertIn("run-migrations-before-tests", found)

        lines = self.store_lines()
        self.assertEqual(len(lines), 3)  # two adds and the promotion mark; nothing removed
        self.assertEqual(lines[-1]["promoted_to"], "AGENTS.md")
        self.assertEqual(lines[-1]["insight"], lines[0]["insight"])

    def test_json_load_hides_promoted_entries_and_stats_counts_them(self):
        self.add("run-migrations-before-tests", "run rake db:migrate first")
        (self.project / "AGENTS.md").write_text("rule\n", encoding="utf-8")
        self.run_memory("promote", "--key", "run-migrations-before-tests", "--to", "AGENTS.md")
        self.assertEqual(json.loads(self.run_memory("load", "--json").stdout), [])
        stats = self.run_memory("stats").stdout
        self.assertIn("TOTAL: 2 line(s), 0 live key(s), 1 promoted", stats)

    def test_readding_the_key_brings_the_entry_back(self):
        self.add("run-migrations-before-tests", "run rake db:migrate first")
        (self.project / "AGENTS.md").write_text("rule\n", encoding="utf-8")
        promoted = self.run_memory("promote", "--key", "run-migrations-before-tests", "--to", "AGENTS.md")
        self.assertIn("PROMOTED", promoted.stdout)
        self.assertNotIn("run-migrations-before-tests", self.run_memory("load").stdout)
        self.add("run-migrations-before-tests", "the AGENTS.md line was dropped; db:migrate still needed")
        shown = self.run_memory("load").stdout
        self.assertIn("the AGENTS.md line was dropped", shown)
        self.assertNotIn("promoted to", shown)
        self.assertNotIn("promoted", self.run_memory("stats").stdout)

    def test_an_absorbed_key_cannot_be_promoted_on_its_own(self):
        self.add("old-wording", "db:migrate first")
        self.add("run-migrations-before-tests", "run rake db:migrate first", "pitfall", "--absorbs", "old-wording")
        refused = self.run_memory("promote", "--key", "old-wording", "--to", "AGENTS.md")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("absorbed into run-migrations-before-tests", refused.stderr)
        self.assertEqual(len(self.store_lines()), 2)
        self.assertIn("1 absorbed", self.run_memory("stats").stdout)

    def test_target_is_normalised_and_checked_against_the_project_root(self):
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        # Without a remote the store is keyed by the directory name, so a subdirectory would be another project.
        subprocess.run(["git", "remote", "add", "origin", "git@example.com:org/repo.git"], cwd=self.project, check=True)
        (self.project / "AGENTS.md").write_text("rule\n", encoding="utf-8")
        (self.project / "src").mkdir()
        self.add("run-migrations-before-tests", "run rake db:migrate first")
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home), PYTHONIOENCODING="utf-8")
        from_subdir = subprocess.run([sys.executable, str(SCRIPT), "promote", "--key", "run-migrations-before-tests",
                                      "--to", "./docs/../AGENTS.md"], cwd=self.project / "src", env=env,
                                     capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(from_subdir.returncode, 0, from_subdir.stderr)
        self.assertEqual(from_subdir.stderr, "")  # the file exists at the root, so no warning
        self.assertEqual(from_subdir.stdout.strip(), "PROMOTED run-migrations-before-tests -> AGENTS.md")
        self.assertEqual(self.store_lines()[-1]["promoted_to"], "AGENTS.md")

    def test_promoting_twice_is_reported_and_adds_no_line(self):
        self.add("run-migrations-before-tests", "run rake db:migrate first")
        (self.project / "AGENTS.md").write_text("rule\n", encoding="utf-8")
        self.run_memory("promote", "--key", "run-migrations-before-tests", "--to", "AGENTS.md")
        again = self.run_memory("promote", "--key", "run-migrations-before-tests", "--to", "AGENTS.md")
        self.assertEqual(again.returncode, 0)
        self.assertIn("ALREADY_PROMOTED", again.stdout)
        self.assertEqual(len(self.store_lines()), 2)

    def test_unknown_key_is_refused_and_missing_target_file_is_warned_about(self):
        refused = self.run_memory("promote", "--key", "never-recorded", "--to", "AGENTS.md")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("no entry with key", refused.stderr)

        self.add("run-migrations-before-tests", "run rake db:migrate first")
        warned = self.run_memory("promote", "--key", "run-migrations-before-tests", "--to", "engineering/architecture.md")
        self.assertEqual(warned.returncode, 0)
        self.assertIn("does not exist", warned.stderr)
        self.assertIn("PROMOTED", warned.stdout)

    def test_target_must_be_a_path_inside_the_repository(self):
        self.add("run-migrations-before-tests", "run rake db:migrate first")
        for bad in ("/etc/AGENTS.md", "../AGENTS.md", "docs/../../AGENTS.md", "C:/repo/AGENTS.md"):
            refused = self.run_memory("promote", "--key", "run-migrations-before-tests", "--to", bad)
            self.assertEqual(refused.returncode, 2, bad)
            self.assertIn("relative to its root", refused.stderr)
        self.assertEqual(len(self.store_lines()), 1)

    def test_promoted_entry_keeps_what_it_absorbed_hidden(self):
        self.add("old-wording", "db:migrate first")
        self.add("run-migrations-before-tests", "run rake db:migrate first", "pitfall", "--absorbs", "old-wording")
        (self.project / "AGENTS.md").write_text("rule\n", encoding="utf-8")
        self.run_memory("promote", "--key", "run-migrations-before-tests", "--to", "AGENTS.md")
        self.assertIn("NO_LEARNINGS", self.run_memory("load").stdout)
        everything = self.run_memory("load", "--all").stdout
        self.assertIn("(absorbs old-wording)", everything)
        self.assertNotIn("**old-wording**", everything)

    def test_reminder_names_promotion(self):
        self.add("node-18-only-here", "nvm use 20 here")
        shown = self.run_memory("load").stdout
        self.assertIn("%s promote --key" % SCRIPT, shown)
        self.assertIn("holds on any machine", shown)


if __name__ == "__main__":
    unittest.main()
