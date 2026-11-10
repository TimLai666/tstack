"""check_stack.py against small stacks built in a temporary directory."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent / "check_stack.py"
CORE = "software-engineering-guidelines"


def skill(name, body="", description=None, version='"1.0.0"'):
    description = description or "This skill MUST be used for %s work." % name
    return ('---\nname: %s\ndescription: "%s"\nmetadata:\n  version: %s\n---\n\n%s\n'
            % (name, description, version, body))


class CheckStack(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.write(".claude-plugin/plugin.json", json.dumps({"name": "tstack", "description": "d", "version": "1.0.0"}))
        self.write(".claude-plugin/marketplace.json", json.dumps(
            {"name": "tstack", "plugins": [{"name": "tstack", "source": "./", "description": "d"}]}))
        self.write("hooks/hooks.json", "{}")
        self.write("README.md", "內容是 4 個 skill。\n\n## Skills\n\n| Skill | 用途 |\n|---|---|\n"
                   "| `%s` | 核心 |\n| `investigate` | 除錯 |\n| `agent-delegation` | 派工 |\n| `project-memory` | 記憶 |\n" % CORE)
        self.write("skills/%s/SKILL.md" % CORE, skill(
            CORE, "## The Stack\n\n| When | Use |\n|---|---|\n| a | **investigate** |\n| b | **agent-delegation** |\n"
                  "| c | **project-memory** |\n\n## Shared Conventions\n\n### Secrets\n\nNever print them.\n"))
        self.write("skills/investigate/SKILL.md", skill(
            "investigate", "Follow [Secrets](../%s/SKILL.md#secrets). Record through **project-memory**." % CORE))
        self.write("skills/agent-delegation/SKILL.md", skill("agent-delegation", "Uses **project-memory**."))
        self.write("skills/project-memory/SKILL.md", skill("project-memory", "Stores lessons."))

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def append(self, relative, text):
        path = self.root / relative
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    def check(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root)],
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
        return result.returncode, result.stdout + result.stderr

    def assertProblem(self, fragment):
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn(fragment, out)

    def test_consistent_stack_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_missing_link_target(self):
        self.append("skills/investigate/SKILL.md", "\nSee [notes](references/missing.md).\n")
        self.assertProblem("references/missing.md")

    def test_missing_anchor(self):
        self.append("skills/investigate/SKILL.md", "\nSee [x](../%s/SKILL.md#no-such-heading).\n" % CORE)
        self.assertProblem("#no-such-heading")

    def test_links_inside_code_blocks_are_ignored(self):
        self.append("skills/investigate/SKILL.md", "\n```md\n[example](does/not/exist.md)\n```\n")
        self.assertEqual(self.check()[0], 0)

    def test_core_must_not_link_into_a_stage_skill(self):
        self.append("skills/%s/SKILL.md" % CORE, "\nSee [steps](../investigate/SKILL.md).\n")
        self.assertProblem("core must not link into")

    def test_service_must_not_reference_a_stage_skill(self):
        self.append("skills/agent-delegation/SKILL.md", "\nThen run **investigate**.\n")
        self.assertProblem("service must not reference stage skill")

    def test_skill_missing_from_routing_table(self):
        self.write("skills/ship-it/SKILL.md", skill("ship-it"))
        self.append("README.md", "| `ship-it` | 交付 |\n")
        self.write("README.md", (self.root / "README.md").read_text(encoding="utf-8").replace("4 個 skill", "5 個 skill"))
        self.assertProblem("not in the core's routing table")

    def test_reference_to_unknown_skill(self):
        self.append("skills/investigate/SKILL.md", "\nHand over to **diff-inspector**.\n")
        self.assertProblem("unknown skill")

    def test_fallback_for_a_missing_skill(self):
        self.append("skills/investigate/SKILL.md", "\nUse **project-memory** when it is installed.\n")
        self.assertProblem("whole")

    def test_fallback_for_a_skill_shipped_elsewhere_is_allowed(self):
        self.append("skills/investigate/SKILL.md", "\nUse the openspec skill if it is installed.\n")
        self.assertEqual(self.check()[0], 0)

    def test_frontmatter_rules(self):
        self.write("skills/investigate/SKILL.md", skill("other-name", "x"))
        self.assertProblem("name must equal the folder name")
        self.write("skills/investigate/SKILL.md", skill("investigate", "x", description="Use it for bugs."))
        self.assertProblem("MUST")
        self.write("skills/investigate/SKILL.md", skill("investigate", "x", description="MUST " + "x" * 1030))
        self.assertProblem("1024")
        self.write("skills/investigate/SKILL.md", skill("investigate", "x", version="1.0"))
        self.assertProblem("version")

    def test_readme_out_of_sync(self):
        self.write("skills/ship-it/SKILL.md", skill("ship-it"))
        self.append("skills/%s/SKILL.md" % CORE, "\n| d | **ship-it** |\n")
        self.assertProblem("README")

    def test_plugin_and_marketplace_descriptions_differ(self):
        self.write(".claude-plugin/plugin.json", json.dumps({"name": "tstack", "description": "other", "version": "1.0.0"}))
        self.assertProblem("description")

    def test_help_describes_the_checks(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0)
        self.assertIn("routing table", result.stdout)


if __name__ == "__main__":
    unittest.main()
