"""The command guard, checked both as a function and as Claude Code would run it."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parent / "guard.py"
_spec = importlib.util.spec_from_file_location("guard", SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


class Rules(unittest.TestCase):
    def blocked(self, command, expected, windows=False):
        self.assertEqual(guard.violation(command, windows=windows), expected, command)

    def allowed(self, command, windows=False):
        self.assertIsNone(guard.violation(command, windows=windows), command)

    def test_git_add_everything_is_blocked(self):
        for command in ("git add -A", "git add --all", "git add .", "git add -Av", "git -C repo add -A",
                        "cd repo && git add . && git commit -m x", "FOO=1 git add -A", "git add -A; git status"):
            self.blocked(command, guard.ADD_ALL)

    def test_git_add_with_paths_is_allowed(self):
        for command in ("git add -- src/a.py docs/b.md", "git add src/", "git add -p src/a.py", "git add ./src/a.py",
                        "git add -u src", "git status --short", "git add .gitignore"):
            self.allowed(command)

    def test_git_commit_all_is_blocked(self):
        for command in ("git commit -a", "git commit -am 'x'", "git commit -ma x", "git commit --all -m x"):
            self.blocked(command, guard.COMMIT_ALL)

    def test_ordinary_commit_is_allowed_even_when_the_message_mentions_blocked_commands(self):
        for command in ("git commit -m 'x'", "git commit --amend --no-edit",
                        "git commit -m \"stop using git add -A; killall node\"",
                        "git commit -m 'docs: glab mr merge && git add .'"):
            self.allowed(command)

    def test_global_git_config_writes_are_blocked_and_reads_allowed(self):
        for command in ("git config --global safe.directory /repo", "git config --global --add safe.directory '*'",
                        "git config --system core.autocrlf true", "git config --global --unset user.name"):
            self.blocked(command, guard.GLOBAL_CONFIG)
        for command in ("git config --global --get user.name", "git config --global user.name", "git config --global --list",
                        "git config core.autocrlf false", "git -c safe.directory=/repo status", "git config --global -l"):
            self.allowed(command)

    def test_merge_request_merge_needs_pinned_sha_and_no_auto_merge(self):
        for command in ("glab mr merge 12", "glab mr merge 12 --auto-merge --yes", "glab mr merge 12 --sha abc --yes",
                        "glab mr merge 12 --auto-merge=false", "glab -R g/p mr merge 12 --yes", "glab mr accept 12"):
            self.blocked(command, guard.MERGE)
        for command in ("glab mr merge 12 --sha abc123 --auto-merge=false --yes", "glab mr view 12", "glab mr list",
                        "glab mr create --title merge", "gh pr merge 3 --match-head-commit abc"):
            self.allowed(command)

    def test_killing_by_name_is_blocked_and_by_pid_allowed(self):
        for command in ("taskkill /IM EXCEL.EXE /F", "taskkill /f /im python.exe", "Stop-Process -Name WINWORD -Force",
                        "Stop-Process WINWORD -Force", "Get-Process excel | Stop-Process", "pkill -f node", "killall node",
                        "taskkill.exe //IM node.exe"):
            self.blocked(command, guard.KILL_BY_NAME)
        for command in ("taskkill /PID 1234 /F", "Stop-Process -Id 1234", "kill 1234", "kill -9 1234", "kill -TERM -- -1234"):
            self.allowed(command)

    def test_tmp_is_blocked_only_on_windows(self):
        for command in ("echo x > /tmp/out.txt", "python make.py --out=/tmp/a.json", "cat '/tmp/a.json'"):
            self.blocked(command, guard.WINDOWS_TMP, windows=True)
            self.allowed(command)
        for command in ("ls C:/Users/me/tmp/a", "ls ./tmp/a", "echo /tmpfile"):
            self.allowed(command, windows=True)

    def test_unparsable_and_empty_input_is_allowed(self):
        for command in ("", None, 42, "echo \"unbalanced", "Write-Host 'it''s fine'"):
            self.allowed(command)


class Hook(unittest.TestCase):
    def run_hook(self, payload, raw=None, **env):
        result = subprocess.run([sys.executable, str(SCRIPT)], input=raw if raw is not None else json.dumps(payload),
                                capture_output=True, text=True, encoding="utf-8", timeout=20, env=dict(os.environ, **env))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_blocked_command_is_denied_with_the_replacement(self):
        for tool in ("Bash", "PowerShell"):
            out = self.run_hook({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": "git add -A"}})
            data = json.loads(out)["hookSpecificOutput"]
            self.assertEqual((data["hookEventName"], data["permissionDecision"]), ("PreToolUse", "deny"))
            self.assertIn("git add -- <路徑>", data["permissionDecisionReason"])

    def test_allowed_command_malformed_event_and_switch_off_print_nothing(self):
        ok = {"tool_name": "Bash", "tool_input": {"command": "git add -- a.py"}}
        self.assertEqual(self.run_hook(ok), "")
        self.assertEqual(self.run_hook(None, raw="not json"), "")
        self.assertEqual(self.run_hook({"tool_name": "Bash"}), "")
        blocked = {"tool_name": "Bash", "tool_input": {"command": "git add -A"}}
        self.assertEqual(self.run_hook(blocked, TSTACK_GUARD="off"), "")


if __name__ == "__main__":
    unittest.main()
