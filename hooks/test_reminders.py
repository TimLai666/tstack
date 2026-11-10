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
        # A private home: the session-start hook runs the memory script, which moves ~/.mystack.
        self.home = self.root / "home"
        self.home.mkdir()
        self.project = self.root / "demo-project"
        self.project.mkdir()

    def run_hook(self, mode, payload=None, raw=None):
        event = dict(session_id="s1", transcript_path=str(self.transcript), cwd=str(self.project))
        event.update(payload or {})
        result = subprocess.run([sys.executable, str(SCRIPT), mode], input=raw if raw is not None else json.dumps(event),
                                capture_output=True, text=True, encoding="utf-8", timeout=20,
                                env=dict(os.environ, CLAUDE_PLUGIN_DATA=str(self.data),
                                         HOME=str(self.home), USERPROFILE=str(self.home)))
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

    def remember(self, *entries, base=".tstack"):
        path = self.home / base / "projects" / "demo-project" / "learnings.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for key, insight in entries:
                handle.write(json.dumps({"ts": "2026-01-01T00:00:00Z", "type": "pitfall", "key": key,
                                         "insight": insight, "confidence": 8, "source": "test"}, ensure_ascii=False) + "\n")

    def machine_fact(self, key, insight):
        path = self.home / ".tstack" / "machine" / "learnings.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"ts": "2026-01-01T00:00:00Z", "type": "tool", "key": key, "insight": insight,
                                     "confidence": 9, "source": "test"}, ensure_ascii=False) + "\n")

    def test_session_start_carries_global_preferences(self):
        path = self.home / ".tstack" / "global" / "learnings.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"ts": "2026-01-01T00:00:00Z", "type": "preference", "key": "fix-small-visual-flaws",
                                    "insight": "看到明顯的小瑕疵就順手修", "confidence": 9, "source": "test"},
                                   ensure_ascii=False) + "\n", encoding="utf-8")
        text = self.session_start()
        self.assertIn("看到明顯的小瑕疵就順手修", text)
        self.assertNotIn("has no memory yet", text)

    def test_session_start_carries_machine_facts_even_without_project_memory(self):
        self.machine_fact("temp-folder-blocks-exe", "暫存資料夾不能執行 exe")
        text = self.session_start()
        self.assertIn("暫存資料夾不能執行 exe", text)
        self.assertIn("no need to run load again", text)
        self.assertNotIn("has no memory yet", text)

    def test_long_project_memory_still_leaves_machine_facts_in_full(self):
        self.machine_fact("temp-folder-blocks-exe", "暫存資料夾不能執行 exe")
        self.remember(*[("long-rule-%02d" % i, "很長的經驗" * 150) for i in range(20)])
        text = self.session_start()
        self.assertLess(len(text), 10000)
        self.assertIn("long-rule-19", text)
        self.assertIn("暫存資料夾不能執行 exe", text)
        self.assertIn("run load", text)

    def test_reduced_machine_facts_without_project_memory_still_ask_for_a_load(self):
        for i in range(40):
            self.machine_fact("machine-fact-number-%02d" % i, "機器事實" * 70)
        text = self.session_start()
        self.assertLess(len(text), 10000)
        self.assertIn("machine-fact-number-39", text)
        self.assertIn("run load", text)
        self.assertNotIn("no need to run load again", text)

    def session_start(self, **payload):
        return self.context("session-start", "SessionStart", dict(source="startup", **payload))["additionalContext"]

    def test_session_start_carries_the_project_memory(self):
        self.remember(("retry-needs-token", "呼叫付款 API 前要先換新的 token"))
        text = self.session_start()
        self.assertIn("retry-needs-token", text)
        self.assertIn("呼叫付款 API 前要先換新的 token", text)
        self.assertIn("no need to run load again", text)
        self.assertIn("memory.py", text)  # the recording command printed by load

    def test_session_start_without_memory_says_so(self):
        text = self.session_start()
        self.assertIn("has no memory yet", text)
        self.assertNotIn("no need to run load again", text)

    def test_session_start_moves_memory_left_in_the_old_folder(self):
        self.remember(("old-store-rule", "舊位置的經驗"), base=".mystack")
        text = self.session_start()
        self.assertIn("舊位置的經驗", text)
        self.assertFalse((self.home / ".mystack").exists())
        self.assertTrue((self.home / ".tstack" / "projects" / "demo-project" / "learnings.jsonl").exists())

    def test_memory_too_long_for_the_hook_lists_keys_and_asks_for_a_load(self):
        self.remember(*[("long-rule-%02d" % i, "很長的經驗" * 150) for i in range(20)])
        text = self.session_start()
        self.assertLess(len(text), 10000)
        self.assertIn("long-rule-00", text)
        self.assertIn("long-rule-19", text)
        self.assertNotIn("很長的經驗很長的經驗", text)
        self.assertIn("run load", text)
        self.assertNotIn("no need to run load again", text)

    def test_session_start_falls_back_to_the_reminder_when_memory_cannot_be_read(self):
        text = self.session_start(cwd=str(self.root / "no-such-folder"))
        self.assertIn("project-memory", text)
        self.assertIn("load this project's memory", text)
        self.assertNotIn("no need to run load again", text)

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
        matchers = {hook["command"].rsplit(" ", 1)[-1]: group["matcher"]
                    for groups in config.values() for group in groups for hook in group["hooks"]}
        self.assertEqual(set(matchers["session-start"].split("|")), {"startup", "resume", "clear", "compact", "fork"})
        self.assertEqual(matchers["post-bash"], "Bash|PowerShell")

    def test_commit_from_powershell_also_reminds(self):
        for command in ("git commit -m 'x'; git push", "git -C repo commit -m \"fix: y\""):
            out = self.context("post-bash", "PostToolUse", {"tool_name": "PowerShell", "tool_input": {"command": command}})
            self.assertIn("project-memory", out["additionalContext"])

    def test_forked_session_gets_the_memory_too(self):
        self.remember(("retry-needs-token", "呼叫付款 API 前要先換新的 token"))
        text = self.context("session-start", "SessionStart", {"source": "fork"})["additionalContext"]
        self.assertIn("呼叫付款 API 前要先換新的 token", text)


if __name__ == "__main__":
    unittest.main()
