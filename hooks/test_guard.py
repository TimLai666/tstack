"""The command guard, checked both as a function and as Claude Code would run it."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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

    def test_merge_request_merge_needs_pinned_sha_and_an_explicit_auto_merge_choice(self):
        for command in ("glab mr merge 12", "glab mr merge 12 --auto-merge --yes", "glab mr merge 12 --sha abc --yes",
                        "glab mr merge 12 --auto-merge=false", "glab -R g/p mr merge 12 --yes", "glab mr accept 12"):
            self.blocked(command, guard.MERGE)
        for command in ("glab mr merge 12 --sha abc123 --auto-merge=false --yes", "glab mr merge 12 --sha abc123 --auto-merge --yes",
                        "glab mr merge 12 --sha=abc123 --auto-merge=true", "glab mr view 12", "glab mr list",
                        "glab mr create --title merge", "gh pr merge 3 --match-head-commit abc"):
            self.allowed(command)

    def test_commands_the_skills_prescribe_are_not_blocked(self):
        for command in ("git add --renormalize .", "git add -- src/a.py", "git commit -m 'chore: normalize line endings'",
                        "git -c safe.directory=/repo status", "git push origin main", "kill 1234",
                        'glab mr merge 7 --sha "$_SHIP_SHA" --auto-merge=false --yes',
                        'glab mr merge 7 --sha "$_SHIP_SHA" --auto-merge --yes',
                        'gh pr merge 7 --match-head-commit "$_SHIP_SHA"', 'gh pr merge 7 --auto --match-head-commit "$_SHIP_SHA"'):
            self.allowed(command)
        self.blocked("git add --renormalize . && git add -A", guard.ADD_ALL)

    def test_killing_by_name_is_blocked_and_by_pid_allowed(self):
        for command in ("taskkill /IM EXCEL.EXE /F", "taskkill /f /im python.exe", "Stop-Process -Name WINWORD -Force",
                        "Stop-Process WINWORD -Force", "Get-Process excel | Stop-Process", "pkill -f node", "killall node",
                        "taskkill.exe //IM node.exe"):
            self.blocked(command, guard.KILL_BY_NAME)
        for command in ("taskkill /PID 1234 /F", "Stop-Process -Id 1234", "kill 1234", "kill -9 1234", "kill -TERM -- -1234"):
            self.allowed(command)

    def test_asking_whether_a_command_exists_is_not_running_it(self):
        for command in ("command -v pkill", "command -V killall", "command -v git add -A", "which pkill", "type killall"):
            self.allowed(command)
        self.blocked("command pkill node", guard.KILL_BY_NAME)
        self.blocked("sudo --user root git add -A", guard.ADD_ALL)
        self.blocked("env --chdir /repo git commit -am x", guard.COMMIT_ALL)

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
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.data = Path(tmp.name) / "plugin-data"
        self.home.mkdir()

    def run_hook(self, payload, raw=None, **env):
        # A private home: host facts are read from ~/.tstack and must never come from the real one.
        base = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home), CLAUDE_PLUGIN_DATA=str(self.data))
        base.update(env)
        result = subprocess.run([sys.executable, str(SCRIPT)], input=raw if raw is not None else json.dumps(payload),
                                capture_output=True, text=True, encoding="utf-8", timeout=20, env=base)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_blocked_command_is_denied_with_the_replacement(self):
        for tool in ("Bash", "PowerShell"):
            out = self.run_hook({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": "git add -A"}})
            data = json.loads(out)["hookSpecificOutput"]
            self.assertEqual((data["hookEventName"], data["permissionDecision"]), ("PreToolUse", "deny"))
            self.assertIn("git add -- <path>", data["permissionDecisionReason"])

    def test_allowed_command_malformed_event_and_switch_off_print_nothing(self):
        ok = {"tool_name": "Bash", "tool_input": {"command": "git add -- a.py"}}
        self.assertEqual(self.run_hook(ok), "")
        self.assertEqual(self.run_hook(None, raw="not json"), "")
        self.assertEqual(self.run_hook({"tool_name": "Bash"}), "")
        blocked = {"tool_name": "Bash", "tool_input": {"command": "git add -A"}}
        self.assertEqual(self.run_hook(blocked, TSTACK_GUARD="off"), "")


class HostTargets(unittest.TestCase):
    def targets(self, command):
        return guard.remote_hosts(command)

    def test_ssh_like_commands_name_their_host(self):
        cases = {
            "ssh devbox": ["devbox"],
            "ssh user@DevBox.local uptime": ["devbox.local"],
            "ssh -p 2222 -i ~/.ssh/key -o StrictHostKeyChecking=no deploy@prod-api 'ls /srv'": ["prod-api"],
            "ssh -J jump devbox": ["devbox"],
            "mosh devbox": ["devbox"],
            "sftp deploy@devbox": ["devbox"],
            "scp build.tar.gz deploy@devbox:/srv/app/": ["devbox"],
            "scp -P 2222 devbox:/var/log/app.log ./logs/": ["devbox"],
            "rsync -az ./dist/ devbox:/srv/www/": ["devbox"],
            "cd app && ssh devbox 'docker ps' | head": ["devbox"],
            "ssh devbox && scp a prod-api:/tmp/a": ["devbox", "prod-api"],
            "sftp -P 2222 devbox": ["devbox"],
            "ssh -vp 2222 devbox": ["devbox"],
            "ssh -p2222 devbox": ["devbox"],
            "mosh --port 60001 devbox": ["devbox"],
            "mosh --ssh='ssh -p 2222' devbox": ["devbox"],
            "sudo -u root ssh devbox": ["devbox"],
            "env -i TERM=xterm ssh devbox": ["devbox"],
            "ssh ssh://deploy@devbox:2222": ["devbox"],
            "sftp sftp://devbox/srv": ["devbox"],
            "rsync -a rsync://devbox/module ./x": ["devbox"],
            "rsync -az -e 'ssh -p 2222' ./dist/ devbox:/srv/www/": ["devbox"],
            "scp -3 host-a:file host-b:file": ["host-a", "host-b"],
            "sudo --user root ssh devbox": ["devbox"],
            "sudo --user=root ssh devbox": ["devbox"],
            "env --unset FOO ssh devbox": ["devbox"],
        }
        for command, expected in cases.items():
            self.assertEqual(self.targets(command), expected, command)

    def test_local_commands_and_paths_name_no_host(self):
        for command in ("ls -la", "git push origin main", "scp a.txt b.txt", "rsync -a ./src/ ./backup/",
                        "cp C:/Users/me/a.txt D:/b.txt", "ssh", "ssh -V", "echo 'ssh devbox'", "ssh-keygen -t ed25519",
                        "rsync -a /var/data/ /mnt/backup/", "scp ./a:b ./c", "command -v ssh", "command -V ssh devbox"):
            self.assertEqual(self.targets(command), [], command)


class HostFacts(Hook):
    def fact(self, host, key, insight):
        path = self.home / ".tstack" / "hosts" / host / "learnings.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"ts": "2026-01-01T00:00:00Z", "type": "tool", "key": key, "insight": insight,
                                     "confidence": 9, "source": "test"}, ensure_ascii=False) + "\n")

    def bash(self, command, session="s1", **env):
        return self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": session,
                              "tool_input": {"command": command}}, **env)

    def test_first_connection_to_a_host_with_facts_is_denied_with_the_facts(self):
        self.fact("devbox", "docker-needs-sudo", "devbox 上 docker 要加 sudo")
        data = json.loads(self.bash("ssh deploy@devbox 'docker ps'"))["hookSpecificOutput"]
        self.assertEqual(data["permissionDecision"], "deny")
        self.assertIn("devbox 上 docker 要加 sudo", data["permissionDecisionReason"])
        self.assertIn("run the same command again", data["permissionDecisionReason"])

    def test_the_same_host_is_not_denied_twice_in_a_session_but_is_in_another(self):
        self.fact("devbox", "docker-needs-sudo", "devbox 上 docker 要加 sudo")
        self.assertIn("deny", self.bash("ssh devbox"))
        self.assertEqual(self.bash("ssh devbox uptime"), "")
        self.assertEqual(self.bash("scp a devbox:/tmp/a"), "")
        self.assertIn("deny", self.bash("ssh devbox", session="s2"))

    def test_each_host_gets_its_own_notice_and_hosts_without_facts_pass(self):
        self.fact("devbox", "docker-needs-sudo", "devbox 上 docker 要加 sudo")
        self.fact("prod-api", "deploy-user-only", "prod-api 只能用 deploy 帳號登入")
        self.assertEqual(self.bash("ssh staging uptime"), "")
        self.assertIn("docker 要加 sudo", self.bash("ssh devbox"))
        self.assertIn("deploy 帳號", self.bash("ssh prod-api"))

    def test_a_dangerous_command_is_reported_before_host_facts(self):
        self.fact("devbox", "docker-needs-sudo", "devbox 上 docker 要加 sudo")
        out = json.loads(self.bash("git add -A && ssh devbox"))["hookSpecificOutput"]
        self.assertIn("git add -- <path>", out["permissionDecisionReason"])

    def test_without_a_place_to_remember_it_adds_context_instead_of_denying(self):
        self.fact("devbox", "docker-needs-sudo", "devbox 上 docker 要加 sudo")
        data = json.loads(self.bash("ssh devbox", CLAUDE_PLUGIN_DATA=""))["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", data)
        self.assertIn("docker 要加 sudo", data["additionalContext"])

    def test_long_host_records_are_cut_to_fit_and_say_how_to_read_the_rest(self):
        for i in range(40):
            self.fact("devbox", "host-fact-number-%02d" % i, "主機事實" * 70)
        reason = json.loads(self.bash("ssh devbox"))["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertLess(len(reason), 9000)
        self.assertIn("host-fact-number-00", reason)
        self.assertIn("load --host devbox", reason)
        self.assertIn("run the same command again", reason)

    def test_a_host_already_shown_is_not_read_again(self):
        self.fact("devbox", "docker-needs-sudo", "devbox 上 docker 要加 sudo")
        self.assertIn("deny", self.bash("ssh devbox"))
        store = self.home / ".tstack" / "hosts" / "devbox" / "learnings.jsonl"
        store.write_text("{not json\n", encoding="utf-8")  # would yield nothing if it were read again
        legacy = self.home / ".mystack"
        legacy.mkdir()
        self.assertEqual(self.bash("ssh devbox uptime"), "")
        self.assertTrue(legacy.exists(), "the memory script ran again and moved the old store")

    def test_old_markers_are_cleaned_up(self):
        self.fact("devbox", "docker-needs-sudo", "devbox 上 docker 要加 sudo")
        folder = self.data / "host-facts-shown"
        folder.mkdir(parents=True)
        old = folder / "ancient--devbox.flag"
        old.touch()
        os.utime(old, (0, 0))
        self.assertIn("deny", self.bash("ssh devbox"))
        self.assertFalse(old.exists())

    def test_wrapped_dangerous_commands_are_still_caught(self):
        out = json.loads(self.bash("sudo -u root git add -A"))["hookSpecificOutput"]
        self.assertIn("git add -- <path>", out["permissionDecisionReason"])

    def test_switch_off_and_unreadable_facts_never_block(self):
        self.fact("devbox", "docker-needs-sudo", "devbox 上 docker 要加 sudo")
        self.assertEqual(self.bash("ssh devbox", TSTACK_GUARD="off"), "")
        broken = self.home / ".tstack" / "hosts" / "broken" / "learnings.jsonl"
        broken.parent.mkdir(parents=True)
        broken.write_text("{not json\n", encoding="utf-8")
        self.assertEqual(self.bash("ssh broken"), "")


if __name__ == "__main__":
    unittest.main()
