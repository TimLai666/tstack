#!/usr/bin/env python3
"""Stop a handful of shell commands that keep causing damage, and say what to run instead.

Usage: guard.py, with the PreToolUse hook event JSON on stdin.
A matching command is denied with the replacement in the reason. Anything this
script cannot parse is let through, and any error prints nothing and exits 0.

It also hands over what project-memory holds about a remote host: the first
command in a session that connects to a host with recorded facts is denied once,
with those facts in the reason, so they are read before anything runs there.

Set TSTACK_GUARD=off in the environment Claude Code starts from to switch it off.
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

OPERATORS = {"&&", "||", ";", "|", "&", "|&", ";;", "(", ")"}
WRAPPERS = {"sudo", "command", "env", "time", "nohup", "exec"}
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
CONFIG_READS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l",
                "--show-origin", "--show-scope", "get", "list"}

ADD_ALL = ("`git add -A`、`git add --all`、`git add .` 會把不屬於這次範圍的檔案一起加進去。"
           "先跑 `git status --short`，再用 `git add -- <路徑> <路徑>` 逐一列出要交付的檔案。")
COMMIT_ALL = ("`git commit -a` 會把所有已追蹤的改動一起提交。"
              "先用 `git add -- <路徑>` 列出這次要交付的檔案，再執行不帶 -a 的 `git commit`。")
GLOBAL_CONFIG = ("不改 git 的全域或系統設定。只影響這一次指令時用 `git -c <名稱>=<值> <指令>`，"
                 "例如 `git -c safe.directory=<路徑> status`；確實要長期生效時，請使用者自己設定。")
MERGE = ("`glab mr merge` 不寫明時預設開啟 auto-merge，還沒有 pipeline 就會直接合併。"
         "一律加上 `--sha <MR 目前的 head commit SHA>`，並寫明要哪一種："
         "該 SHA 已經全綠就用 `--auto-merge=false` 立刻合併；"
         "檢查還在跑、要全綠後合併，而且平台等的條件與全綠相同時，才用 `--auto-merge` 交給平台等。"
         "該 SHA 還沒有 pipeline 時兩種都不要下，先等 pipeline 出現。細節見 ship-it 的 Step 8。")
KILL_BY_NAME = ("不依程式名稱結束程序，同名的程序可能是使用者或其他流程開的。"
                "只結束自己啟動的那一個：POSIX 用 `kill <PID>`，Windows 用 `taskkill /PID <PID>` 或 `Stop-Process -Id <PID>`。")
HOST_FACTS = ("連到 %s 之前，先讀 project-memory 裡這台主機的記錄：\n\n%s\n\n"
              "讀完後重新執行同一個指令。這個提醒在每段對話裡，每台主機只出現一次。")
MEMORY_SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "project-memory" / "scripts" / "memory.py"
# ssh options that take a value, so the word after them is not the host.
SSH_VALUE_OPTIONS = set("bcDEeFIiJLlmOopQRSWw")
REMOTE_PATH = re.compile(r"^(?:[^@/\\:\s]+@)?([A-Za-z0-9][A-Za-z0-9._-]*):")

WINDOWS_TMP = ("Windows 上各個 shell 與程式對 `/tmp` 的解讀不同，寫進去的檔案別的程式讀不到。"
               "改用這個 session 的暫存目錄或專案內的絕對路徑。")


def segments(command):
    """Split a command line into simple commands, each a list of words."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:  # Unbalanced quotes, usually PowerShell syntax: fall back to a plain split.
        tokens = re.sub(r"(&&|\|\||[;|\n])", r" \1 ", command).split()
    current = []
    for line in "\n".join(tokens).split("\n"):
        if line in OPERATORS or not line:
            if current:
                yield current
            current = []
        else:
            current.append(line)
    if current:
        yield current


def strip_prefix(words):
    """Drop leading VAR=value assignments and wrappers such as sudo or env."""
    i = 0
    while i < len(words) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i]) or words[i] in WRAPPERS):
        i += 1
    return words[i:]


def program(word):
    name = re.split(r"[\\/]", word)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def short_flags(words):
    return "".join(w[1:] for w in words if re.match(r"^-[A-Za-z]+$", w))


def check_git(args):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_VALUE_OPTIONS else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    if sub == "add":
        if "--renormalize" in rest:
            return None  # Rewrites line endings of tracked files only; the core prescribes it for a new .gitattributes.
        if "--all" in rest or "." in rest or "A" in short_flags(rest):
            return ADD_ALL
    elif sub == "commit":
        if "--all" in rest or "a" in short_flags(rest):
            return COMMIT_ALL
    elif sub == "config":
        if not ({"--global", "--system"} & set(rest)) or CONFIG_READS & set(rest):
            return None
        positional = [w for w in rest if not w.startswith("-")]
        if len(positional) >= 2 or {"--add", "--unset", "--unset-all", "--replace-all", "--edit", "-e"} & set(rest):
            return GLOBAL_CONFIG
    return None


def check_segment(words):
    words = strip_prefix(words)
    if not words:
        return None
    name, args = program(words[0]), words[1:]
    lowered = [a.lower() for a in args]
    if name == "git":
        return check_git(args)
    if name == "glab":
        plain = [a for a in lowered if not a.startswith("-")]
        if any(pair in (("mr", "merge"), ("mr", "accept")) for pair in zip(plain, plain[1:])):
            pinned = any(a == "--sha" or a.startswith("--sha=") for a in lowered)
            chosen = any(a == "--auto-merge" or a.startswith("--auto-merge=") for a in lowered)
            if not pinned or not chosen:
                return MERGE
    if name in ("pkill", "killall"):
        return KILL_BY_NAME
    if name == "taskkill" and any(a in ("/im", "-im", "//im") for a in lowered):
        return KILL_BY_NAME
    if name in ("stop-process", "spps") and "-id" not in lowered:
        return KILL_BY_NAME
    if name == "kill" and "-name" in lowered:
        return KILL_BY_NAME
    return None


def host_name(raw):
    """Normalised the way project-memory names a host folder, or None."""
    name = raw.rsplit("@", 1)[-1].strip().lower()
    return name if re.match(r"^[a-z0-9][a-z0-9._-]*$", name) and ".." not in name else None


def remote_hosts(command):
    """Hosts that the ssh, mosh, sftp, scp and rsync commands in this line connect to, in order."""
    found = []
    if not isinstance(command, str):
        return found
    for words in segments(command):
        words = strip_prefix(words)
        if not words:
            continue
        name, args, target = program(words[0]), words[1:], None
        if name in ("ssh", "mosh", "sftp"):
            i = 0
            while i < len(args) and args[i].startswith("-"):
                takes_value = len(args[i]) == 2 and args[i][1] in SSH_VALUE_OPTIONS
                i += 2 if takes_value else 1
            if i < len(args):
                target = host_name(args[i].split(":", 1)[0])
        elif name in ("scp", "rsync"):
            for arg in args:
                match = None if arg.startswith(("-", "/", ".", "~")) else REMOTE_PATH.match(arg)
                if match and len(match.group(1)) > 1:  # a single letter is a Windows drive
                    target = host_name(match.group(1))
                    break
        if target and target not in found:
            found.append(target)
    return found


def host_facts(host):
    """What project-memory recorded about this host, or None when there is nothing to read."""
    store = Path(os.path.expanduser("~")) / ".tstack" / "hosts" / host / "learnings.jsonl"
    if not store.is_file():
        return None
    result = subprocess.run([sys.executable, str(MEMORY_SCRIPT), "load", "--host", host], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=6,
                            env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    text = result.stdout.strip()
    return text if result.returncode == 0 and text.startswith("# Host memory") else None


def first_time(session, host):
    """True the first time this session meets this host, None on later ones, False when nothing can be kept."""
    root = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not root:
        return False
    folder = Path(root) / "host-facts-shown"
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / (re.sub(r"[^A-Za-z0-9_-]", "_", session or "unknown") + "--" + host + ".flag")
    if marker.exists():
        return None
    marker.touch()
    return True


def host_notice(command, session):
    """(facts text, deny?) for the first host in the command whose facts were not shown yet, or None."""
    for host in remote_hosts(command):
        facts = host_facts(host)
        if not facts:
            continue
        seen = first_time(session, host)
        if seen is None:
            continue
        return HOST_FACTS % (host, facts), bool(seen)
    return None


def violation(command, windows=None):
    """The replacement advice for the first blocked command in the line, or None."""
    if not isinstance(command, str) or not command.strip():
        return None
    windows = os.name == "nt" if windows is None else windows
    if windows and re.search(r"(^|[\s'\"=])/tmp/", command):
        return WINDOWS_TMP
    for words in segments(command):
        reason = check_segment(words)
        if reason:
            return reason
    return None


def main():
    try:
        if os.environ.get("TSTACK_GUARD", "").lower() == "off":
            return 0
        event = json.loads(sys.stdin.read())
        command = (event.get("tool_input") or {}).get("command")
        reason, deny = violation(command), True
        if not reason:
            notice = host_notice(command, event.get("session_id"))
            if notice:
                reason, deny = notice
    except Exception:  # A guard that crashes must not block work.
        return 0
    if reason:
        # Without a place to remember that it was shown, a denial would repeat forever: add context instead.
        detail = ({"permissionDecision": "deny", "permissionDecisionReason": "tstack guard：" + reason} if deny
                  else {"additionalContext": "tstack guard：" + reason})
        reply = {"hookSpecificOutput": dict(hookEventName="PreToolUse", **detail)}
        # Claude Code reads hook output as UTF-8; Windows consoles default to a legacy code page.
        sys.stdout.buffer.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
