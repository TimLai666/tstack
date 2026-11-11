"""Tests for scripts/migrate_layout.py."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "migrate_layout.py"
STATUS = "# Status\n\n## Next Verifiable Output\nlogin works\n\n## Next Ticket\n03\n"


class MigrateLayoutTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, path, text="x\n"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)

    def test_dry_run_changes_nothing(self):
        self.write("ENG.md")
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertIn("Would move", result.stdout)
        self.assertIn("ENG.md -> engineering/architecture.md", result.stdout)
        self.assertTrue((self.root / "ENG.md").exists())
        self.assertFalse((self.root / "engineering").exists())

    def test_apply_moves_every_generation(self):
        self.write("delivery-status.md", STATUS)
        self.write("ENG.md")
        self.write("DESIGN-REVIEW.md")
        self.write("docs/tickets/01-a.md")
        self.write("docs/dev/specs/login.md")
        self.write("docs/security-scan/report.md")
        self.write("docs/software-engineering-guidelines/task.md")
        self.write("docs/guide.md")
        result = self.run_script("--apply")
        self.assertEqual(result.returncode, 0, result.stdout)
        for path in ("status.md", "architecture.md", "reviews/ui.md", "tickets/01-a.md", "specs/login.md",
                     "reviews/security.md", "tasks/task.md"):
            self.assertTrue((self.root / "engineering" / path).is_file(), path)
        for path in ("ENG.md", "delivery-status.md", "DESIGN-REVIEW.md", "docs/tickets", "docs/dev",
                     "docs/security-scan", "docs/software-engineering-guidelines"):
            self.assertFalse((self.root / path).exists(), path)
        self.assertTrue((self.root / "docs/guide.md").is_file())
        self.assertIn("engineering/README.md is missing", result.stdout)

    def test_legacy_status_plan_moves_and_feature_plan_stays(self):
        self.write("delivery-plan.md", STATUS)
        self.assertEqual(self.run_script("--apply").returncode, 0)
        self.assertTrue((self.root / "engineering/status.md").is_file())

        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        self.root = Path(other.name)
        self.write("delivery-plan.md", "# Plan: ship faster\n\n## Goal and constraints\n")
        result = self.run_script("--apply")
        self.assertTrue((self.root / "delivery-plan.md").is_file())
        self.assertIn("does not read as a status record", result.stdout)

    def test_existing_destination_blocks_the_move(self):
        self.write("ENG.md", "old\n")
        self.write("engineering/architecture.md", "new\n")
        result = self.run_script("--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stdout)
        self.assertEqual((self.root / "ENG.md").read_text(encoding="utf-8"), "old\n")
        self.assertEqual((self.root / "engineering/architecture.md").read_text(encoding="utf-8"), "new\n")

    def test_two_sources_for_one_destination_block_each_other(self):
        self.write("delivery-plan.md", STATUS)
        self.write("delivery-status.md", STATUS)
        self.write("docs/tickets/01-a.md")
        self.write("docs/dev/tickets/01-a.md")
        result = self.run_script("--apply")
        self.assertEqual(result.returncode, 1)
        self.assertTrue((self.root / "delivery-plan.md").exists())
        self.assertTrue((self.root / "delivery-status.md").exists())
        self.assertTrue((self.root / "docs/tickets/01-a.md").exists())
        self.assertFalse((self.root / "engineering").exists())

    def test_tracked_files_move_with_git(self):
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "test")
        self.write("ENG.md")
        self.write("notes.md")
        self.git("add", "ENG.md")
        self.git("commit", "-q", "-m", "init")
        self.write("docs/tickets/01-a.md")
        self.assertEqual(self.run_script("--apply").returncode, 0)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.root, capture_output=True,
                                text=True).stdout
        self.assertIn("R  ENG.md -> engineering/architecture.md", status)
        self.assertTrue((self.root / "engineering/tickets/01-a.md").is_file())

    def test_lists_remaining_mentions_without_editing(self):
        text = "Read `ENG.md` and `delivery-status.md`. Tickets are in docs/tickets/.\nSee OPENGL_ENG.md too.\n"
        self.write("AGENTS.md", text)
        self.write("engineering/README.md")
        result = self.run_script("--apply")
        self.assertIn("AGENTS.md:1:", result.stdout)
        self.assertNotIn("AGENTS.md:2:", result.stdout)
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8"), text)

    def test_clean_project_reports_nothing(self):
        self.write("README.md", "hello\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "Nothing to move.")


if __name__ == "__main__":
    unittest.main()
