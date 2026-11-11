"""Tests for scripts/migrate_layout.py."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "migrate_layout.py"
STATUS = "# Status\n\n## Next Verifiable Output\nlogin works\n\n## Next Ticket\n03\n"


def ticket(status=None):
    line = f"**Status:** {status}\n" if status else ""
    return f"# 01 — A customer can book\n\n**Epic:** Booking\n**Blocked by:** none\n{line}\n## What it delivers\nx\n"


class MigrateLayoutTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, path, text="x\n"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def text(self, path):
        return (self.root / path).read_text(encoding="utf-8")

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)

    def test_dry_run_changes_nothing(self):
        self.write("ENG.md")
        self.write("docs/tickets/01-a.md", ticket("done"))
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertIn("Would move", result.stdout)
        self.assertIn("ENG.md -> engineering/architecture.md", result.stdout)
        self.assertIn("docs/tickets/01-a.md -> engineering/tickets/done/01-a.md (status field removed)", result.stdout)
        self.assertTrue((self.root / "ENG.md").exists())
        self.assertIn("**Status:** done", self.text("docs/tickets/01-a.md"))
        self.assertFalse((self.root / "engineering").exists())

    def test_apply_moves_every_generation(self):
        self.write("delivery-status.md", STATUS)
        self.write("ENG.md")
        self.write("DESIGN-REVIEW.md")
        self.write("docs/tickets/01-a.md", ticket())
        self.write("docs/dev/specs/login.md")
        self.write("docs/security-scan/report.md")
        self.write("docs/software-engineering-guidelines/task.md")
        self.write("docs/guide.md")
        result = self.run_script("--apply")
        self.assertEqual(result.returncode, 0, result.stdout)
        for path in ("architecture.md", "tickets/01-a.md", "specs/login.md", "reports/legacy-status.md",
                     "reports/legacy-ui-review.md", "reports/legacy-security-scan.md", "reports/task.md"):
            self.assertTrue((self.root / "engineering" / path).is_file(), path)
        for path in ("ENG.md", "delivery-status.md", "DESIGN-REVIEW.md", "docs/tickets", "docs/dev",
                     "docs/security-scan", "docs/software-engineering-guidelines"):
            self.assertFalse((self.root / path).exists(), path)
        self.assertTrue((self.root / "docs/guide.md").is_file())
        self.assertIn("engineering/README.md is missing", result.stdout)
        self.assertIn("Carry over by hand:", result.stdout)
        self.assertIn("engineering/reports/legacy-status.md: write each Decision Log entry", result.stdout)

    def test_tickets_are_filed_by_their_old_status(self):
        self.write("docs/tickets/01-done.md", ticket("done"))
        self.write("docs/tickets/02-doing.md", ticket("in_progress"))
        self.write("docs/tickets/03-ready.md", ticket("ready"))
        self.write("docs/tickets/04-blocked.md", ticket("blocked"))
        self.write("docs/tickets/05-odd.md", ticket("waiting for legal"))
        self.write("docs/tickets/06-none.md", ticket())
        result = self.run_script("--apply")
        self.assertEqual(result.returncode, 0, result.stdout)
        base = "engineering/tickets/"
        for path in ("done/01-done.md", "doing/02-doing.md", "03-ready.md"):
            self.assertNotIn("Status", self.text(base + path), path)
            self.assertIn("**Blocked by:** none\n\n## What it delivers", self.text(base + path))
        self.assertIn("**Blocked:** reason not recorded", self.text(base + "04-blocked.md"))
        self.assertIn("04-blocked.md: its status was blocked", result.stdout)
        self.assertNotIn("**Status:**", self.text(base + "04-blocked.md"))
        self.assertIn("**Status:** waiting for legal", self.text(base + "05-odd.md"))
        self.assertIn("05-odd.md: status 'waiting for legal' is not recognized", result.stdout)
        self.assertEqual(self.text(base + "06-none.md"), ticket())

    def test_status_field_variants(self):
        self.write("docs/tickets/01-a.md", "# 01\n\nStatus: Completed\n\nbody\n")
        self.write("docs/tickets/02-b.md", "# 02\n\n**狀態：** 進行中\n\nbody\n")
        self.write("docs/tickets/03-c.md", "# 03\n\n**Status**: `not_started`\n\nbody\n")
        self.write("docs/tickets/04-d.md", "# 04\n\nThe Status: line is described in prose here.\n")
        self.assertEqual(self.run_script("--apply").returncode, 0)
        base = "engineering/tickets/"
        self.assertEqual(self.text(base + "done/01-a.md"), "# 01\n\n\nbody\n")
        self.assertEqual(self.text(base + "doing/02-b.md"), "# 02\n\n\nbody\n")
        self.assertEqual(self.text(base + "03-c.md"), "# 03\n\n\nbody\n")
        self.assertIn("Status: line is described", self.text(base + "04-d.md"))

    def test_blocked_status_with_blockers_is_only_removed(self):
        body = "# 02\n\n**Blocked by:** [01 scaffold](01-a.md)\n**Status:** blocked\n\nbody\n"
        self.write("docs/tickets/01-a.md", ticket("done"))
        self.write("docs/tickets/02-b.md", body)
        result = self.run_script("--apply")
        self.assertEqual(self.text("engineering/tickets/02-b.md"), "# 02\n\n**Blocked by:** 01 scaffold\n\nbody\n")
        self.assertNotIn("its status was blocked", result.stdout)

    def test_links_survive_the_move(self):
        self.write("src/main.go")
        self.write("docs/guide.md")
        self.write("docs/tickets/README.md", "[01](01-a.md) [guide](../guide.md)\n")
        self.write("docs/tickets/01-a.md", "# 01\n\n**Status:** done\n\n[code](../../src/main.go#L3) [02](02-b.md) "
                                           "[site](https://example.com/a.md) [gone](missing.md) ![shot](../guide.md)\n")
        self.write("docs/tickets/02-b.md", "# 02\n\nSee [01 — first](01-a.md).\n")
        self.write("ENG.md", "[ticket](docs/tickets/01-a.md) [guide](docs/guide.md)\n")
        result = self.run_script("--apply")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.text("engineering/tickets/done/01-a.md"),
                         "# 01\n\n\n[code](/src/main.go#L3) 02 [site](https://example.com/a.md) [gone](missing.md) "
                         "![shot](/docs/guide.md)\n")
        self.assertEqual(self.text("engineering/tickets/02-b.md"), "# 02\n\nSee 01 — first.\n")
        self.assertEqual(self.text("engineering/tickets/README.md"),
                         "[01](/engineering/tickets/done/01-a.md) [guide](/docs/guide.md)\n")
        self.assertEqual(self.text("engineering/architecture.md"),
                         "[ticket](/engineering/tickets/done/01-a.md) [guide](/docs/guide.md)\n")
        self.assertIn("Moved with the tickets", result.stdout)

    def test_handoff_file_is_parked(self):
        self.write("HANDOFF.md")
        result = self.run_script("--apply")
        self.assertTrue((self.root / "engineering/reports/legacy-handoff.md").is_file())
        self.assertIn("legacy-handoff.md: move each note to the ticket it concerns", result.stdout)

    def test_tickets_already_in_place_are_refiled_and_a_second_run_is_clean(self):
        self.write("engineering/README.md")
        self.write("engineering/tickets/01-a.md", ticket("Done"))
        self.write("engineering/tickets/02-b.md", ticket("not_started"))
        first = self.run_script("--apply")
        self.assertEqual(first.returncode, 0, first.stdout)
        self.assertTrue((self.root / "engineering/tickets/done/01-a.md").is_file())
        self.assertIn("engineering/tickets/02-b.md: status field removed", first.stdout)
        self.assertNotIn("Status", self.text("engineering/tickets/02-b.md"))
        second = self.run_script("--apply")
        self.assertEqual(second.stdout.strip(), "Nothing to move.")

    def test_legacy_status_plan_moves_and_feature_plan_stays(self):
        self.write("delivery-plan.md", STATUS)
        self.assertEqual(self.run_script("--apply").returncode, 0)
        self.assertTrue((self.root / "engineering/reports/legacy-status.md").is_file())

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
        self.assertEqual(self.text("ENG.md"), "old\n")
        self.assertEqual(self.text("engineering/architecture.md"), "new\n")

    def test_two_sources_for_one_destination_block_each_other(self):
        self.write("delivery-plan.md", STATUS)
        self.write("delivery-status.md", STATUS)
        self.write("docs/tickets/01-a.md", ticket())
        self.write("docs/dev/tickets/01-a.md", ticket())
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
        self.git("add", "ENG.md")
        self.git("commit", "-q", "-m", "init")
        self.write("docs/tickets/01-a.md", ticket())
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
        self.assertEqual(self.text("AGENTS.md"), text)

    def test_clean_project_reports_nothing(self):
        self.write("README.md", "hello\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "Nothing to move.")


if __name__ == "__main__":
    unittest.main()
