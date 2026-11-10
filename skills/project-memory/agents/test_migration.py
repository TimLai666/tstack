"""The store moved from ~/.mystack to ~/.tstack; every run carries old data over."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "memory.py"


def line(key, insight="lesson", ts="2026-01-01T00:00:00Z"):
    return json.dumps({"ts": ts, "type": "pitfall", "key": key, "insight": insight,
                       "confidence": 8, "source": "test"}, ensure_ascii=False)


class Migration(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.project = Path(tmp.name) / "demo-project"
        self.home.mkdir()
        self.project.mkdir()
        self.old = self.home / ".mystack"
        self.new = self.home / ".tstack"

    def run_memory(self, *args):
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home))
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.project, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=30)

    def write(self, root, slug, *lines):
        path = root / "projects" / slug / "learnings.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(item + "\n" for item in lines), encoding="utf-8")
        return path

    def keys(self, slug="demo-project"):
        path = self.new / "projects" / slug / "learnings.jsonl"
        return [json.loads(item)["key"] for item in path.read_text(encoding="utf-8").splitlines() if item.strip()]

    def test_old_store_moves_whole_including_other_projects_and_stray_files(self):
        self.write(self.old, "demo-project", line("alpha-rule"), line("beta-rule"))
        self.write(self.old, "other-project", line("gamma-rule"))
        (self.old / "notes.txt").write_text("keep me", encoding="utf-8")

        result = self.run_memory("load", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e["key"] for e in json.loads(result.stdout)], ["alpha-rule", "beta-rule"])
        self.assertEqual(self.keys("other-project"), ["gamma-rule"])
        self.assertEqual((self.new / "notes.txt").read_text(encoding="utf-8"), "keep me")
        self.assertFalse(self.old.exists())
        self.assertIn(".tstack", result.stderr)

    def test_path_points_to_new_store_and_fresh_install_creates_nothing_old(self):
        result = self.run_memory("path")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(os.path.join(".tstack", "projects", "demo-project", "learnings.jsonl"), result.stdout)
        self.assertFalse(self.old.exists())
        self.assertEqual(result.stderr, "")

    def test_both_stores_merge_without_losing_or_duplicating_lines(self):
        shared = line("shared-rule")
        self.write(self.new, "demo-project", shared, line("new-only-rule"))
        self.write(self.old, "demo-project", shared, line("old-only-rule"))
        self.write(self.old, "other-project", line("gamma-rule"))

        result = self.run_memory("load", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.keys(), ["shared-rule", "new-only-rule", "old-only-rule"])
        self.assertEqual(self.keys("other-project"), ["gamma-rule"])
        self.assertFalse(self.old.exists())

    def test_old_file_without_trailing_newline_keeps_lines_separate(self):
        new_file = self.write(self.new, "demo-project", line("new-only-rule"))
        new_file.write_text(line("new-only-rule"), encoding="utf-8")  # no trailing newline
        self.write(self.old, "demo-project", line("old-only-rule"))

        self.assertEqual(self.run_memory("stats").returncode, 0)
        self.assertEqual(self.keys(), ["new-only-rule", "old-only-rule"])

    def test_conflicting_non_store_file_stays_in_old_folder(self):
        self.write(self.new, "demo-project", line("new-only-rule"))
        self.write(self.old, "demo-project", line("old-only-rule"))
        (self.new / "notes.txt").write_text("new", encoding="utf-8")
        (self.old / "notes.txt").write_text("old", encoding="utf-8")

        result = self.run_memory("load", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.keys(), ["new-only-rule", "old-only-rule"])
        self.assertEqual((self.new / "notes.txt").read_text(encoding="utf-8"), "new")
        self.assertEqual((self.old / "notes.txt").read_text(encoding="utf-8"), "old")
        self.assertIn("notes.txt", result.stderr)

    def test_writes_after_migration_land_in_new_store_and_rerun_is_quiet(self):
        self.write(self.old, "demo-project", line("alpha-rule"))
        self.assertEqual(self.run_memory("load").returncode, 0)

        added = self.run_memory("add", "--type", "pitfall", "--key", "delta-rule",
                                "--insight", "x", "--confidence", "8")
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertEqual(added.stderr, "")
        self.assertEqual(self.keys(), ["alpha-rule", "delta-rule"])
        self.assertFalse(self.old.exists())

    def test_migrating_unicode_and_damaged_lines_keeps_bytes(self):
        raw = line("unicode-rule", "中文「引號」\\ backslash") + "\n{not json\n"
        path = self.write(self.old, "demo-project")
        path.write_bytes(raw.encode("utf-8"))
        self.write(self.new, "demo-project", line("new-only-rule"))

        self.assertEqual(self.run_memory("stats").returncode, 0)
        merged = (self.new / "projects" / "demo-project" / "learnings.jsonl").read_text(encoding="utf-8")
        self.assertIn(raw, merged)


if __name__ == "__main__":
    unittest.main()
