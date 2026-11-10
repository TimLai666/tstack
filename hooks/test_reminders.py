"""Reminder hooks for the tstack plugin, run as Claude Code would run them."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HOOKS = Path(__file__).resolve().parent
SCRIPT = HOOKS / "reminders.py"


class Reminders(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root / "plugin-data"
        self.transcript = self.root / "session.jsonl"
        self.transcript.write_text("")

    def run_hook(self, mode, payload=None, raw=None):
        event = dict(session_id="s1", transcript_path=str(self.transcript), cwd=str(self.root))
        event.update(payload or {})
        result = subprocess.run([sys.executable, str(SCRIPT), mode], input=raw if raw is not None else json.dumps(event),
                                capture_output=True, text=True, encoding="utf-8", timeout=20,
                                env=dict(os.environ, CLAUDE_PLUGIN_DATA=str(self.data)))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def context(self, mode, event, payload=None):
        out = self.run_hook(mode, dict(hook_event_name=event, **(payload or {})))
        if not out.strip():
            return None
        data = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(data["hookEventName"], event)
        return data

    def record(self, *items):
        with self.transcript.open("a", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    def skill_load(self, name="tstack:agent-delegation"):
        return {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": name}}]}}

    def test_session_start_points_to_all_three_skills(self):
        for source in ("startup", "resume", "compact"):
            with self.subTest(source=source):
                text = self.context("session-start", "SessionStart", {"source": source})["additionalContext"]
                for skill in ("project-memory", "software-engineering-guidelines", "agent-delegation"):
                    self.assertIn(skill, text)

    def test_first_subagent_without_delegation_skill_is_denied_once(self):
        first = self.context("pre-agent", "PreToolUse", {"tool_name": "Agent"})
        self.assertEqual(first["permissionDecision"], "deny")
        self.assertIn("agent-delegation", first["permissionDecisionReason"])
        self.assertIsNone(self.context("pre-agent", "PreToolUse", {"tool_name": "Agent"}))

    def test_loaded_delegation_skill_allows_subagent_silently(self):
        self.record(self.skill_load())
        self.assertIsNone(self.context("pre-agent", "PreToolUse", {"tool_name": "Agent"}))
        self.assertFalse(self.data.exists() and any(self.data.rglob("*")))

    def test_other_skill_does_not_count_as_delegation_skill(self):
        self.record(self.skill_load("tstack:project-memory"))
        self.assertEqual(self.context("pre-agent", "PreToolUse", {"tool_name": "Agent"})["permissionDecision"], "deny")

    def test_skill_loaded_before_compaction_no_longer_counts(self):
        self.record(self.skill_load(), {"type": "system", "subtype": "compact_boundary", "content": "Conversation compacted"})
        self.assertEqual(self.context("pre-agent", "PreToolUse", {"tool_name": "Agent"})["permissionDecision"], "deny")

    def test_each_session_gets_its_own_single_denial(self):
        self.context("pre-agent", "PreToolUse", {"tool_name": "Agent"})
        other = self.context("pre-agent", "PreToolUse", {"tool_name": "Agent", "session_id": "s2"})
        self.assertEqual(other["permissionDecision"], "deny")

    def test_subagents_are_never_reminded(self):
        for mode, event in (("pre-agent", "PreToolUse"), ("post-agent", "PostToolUse")):
            with self.subTest(mode=mode):
                self.assertIsNone(self.context(mode, event, {"tool_name": "Agent", "agent_id": "a1", "agent_type": "Explore"}))

    def test_subagent_return_reminds_to_verify_reported_lessons(self):
        text = self.context("post-agent", "PostToolUse", {"tool_name": "Agent"})["additionalContext"]
        self.assertIn("project-memory", text)

    def test_only_git_commit_reminds_to_record_lessons(self):
        commits = ["git commit -m 'fix: x'", "git add -A && git commit -F msg.txt", "git -C repo commit -q -m x"]
        others = ["git status", "git commit --dry-run -m x", "echo 'git commit'", "python3 -m unittest"]
        for command in commits:
            with self.subTest(command=command):
                text = self.context("post-bash", "PostToolUse", {"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertIn("project-memory", text["additionalContext"])
        for command in others:
            with self.subTest(command=command):
                self.assertIsNone(self.context("post-bash", "PostToolUse", {"tool_name": "Bash", "tool_input": {"command": command}}))

    def test_compaction_summary_keeps_unrecorded_lessons(self):
        out = self.run_hook("pre-compact", dict(hook_event_name="PreCompact", trigger="auto"))
        self.assertIn("project-memory", out)
        self.assertFalse(out.lstrip().startswith("{"))

    def test_broken_input_never_blocks_work(self):
        for mode in ("session-start", "pre-agent", "post-agent", "post-bash", "pre-compact", "unknown"):
            with self.subTest(mode=mode):
                self.assertEqual(self.run_hook(mode, raw="not json"), "")

    def test_missing_transcript_still_reminds_once(self):
        self.transcript.unlink()
        self.assertEqual(self.context("pre-agent", "PreToolUse", {"tool_name": "Agent"})["permissionDecision"], "deny")
        self.assertIsNone(self.context("pre-agent", "PreToolUse", {"tool_name": "Agent"}))

    def test_hook_config_routes_every_event_to_an_existing_mode(self):
        config = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        expected = {("SessionStart", "session-start"), ("PreToolUse", "pre-agent"), ("PostToolUse", "post-agent"),
                    ("PostToolUse", "post-bash"), ("PreCompact", "pre-compact")}
        seen, guards = set(), []
        for event, groups in config.items():
            for group in groups:
                for hook in group["hooks"]:
                    self.assertEqual(hook["type"], "command")
                    if "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py" in hook["command"]:
                        guards.append((event, group["matcher"]))
                        continue
                    self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/reminders.py", hook["command"])
                    seen.add((event, hook["command"].rsplit(" ", 1)[-1]))
        self.assertEqual(seen, expected)
        self.assertEqual(guards, [("PreToolUse", "Bash|PowerShell")])


if __name__ == "__main__":
    unittest.main()
