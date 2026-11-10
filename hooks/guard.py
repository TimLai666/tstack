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
import time

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
# Hook context over 10,000 characters is replaced by a preview, so the notice stays well under it.
NOTICE_BUDGET = 8000
HOST_FACTS_CUT = "\n… 這台主機的記錄太長，放不下全文。用 project-memory 的 `load --host %s` 讀完整內容。"
LOOKUP_SECONDS = 6
# Short options that take a value, so the word after them is not the host.
VALUE_OPTIONS = {"ssh": set("bcDEeFIiJLlmOopQRSWw"), "mosh": set("p"), "sftp": set("BbcDFiJlPoRSsX"),
                 "scp": set("cDFiJloPSX"), "rsync": set("eMT")}
LONG_VALUE_OPTIONS = {"--port", "--ssh", "--server", "--predict", "--family", "--bind-server", "--client", "--rsh"}
WRAPPER_VALUE_OPTIONS = {"sudo": set("ughpCDRTU"), "env": set("uSC"), "time": set("fo"), "exec": set("a")}
WRAPPER_LONG_VALUE_OPTIONS = {"--user", "--group", "--host", "--prompt", "--chdir", "--chroot", "--role", "--type",
                              "--other-user", "--close-from", "--command-timeout", "--unset", "--split-string"}
REMOTE_PATH = re.compile(r"^(?:[^@/\\:\s]+@)?([A-Za-z0-9][A-Za-z0-9._-]*):")
REMOTE_URL = re.compile(r"^(?:ssh|sftp|scp|rsync)://(?:[^@/\s]+@)?([A-Za-z0-9][A-Za-z0-9._-]*)")

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


def skip_options(args, value_options, long_value_options=LONG_VALUE_OPTIONS):
    """Index of the first word that is not an option or an option's value."""
    i = 0
    while i < len(args) and args[i].startswith("-") and args[i] != "-":
        word = args[i]
        if word == "--":
            return i + 1
        takes_next = word in long_value_options
        if not word.startswith("--"):
            # In a cluster such as -vp, only an option that ends the word takes the next word as its value.
            for position, letter in enumerate(word[1:], 1):
                if letter in value_options:
                    takes_next = position == len(word) - 1
                    break
        i += 2 if takes_next else 1
    return i


def strip_prefix(words):
    """Drop leading VAR=value assignments and wrappers such as sudo or env, with the wrappers' own options."""
    i = 0
    while i < len(words):
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i]):
            i += 1
        elif words[i] in WRAPPERS:
            if words[i] == "command" and words[i + 1:i + 2] in (["-v"], ["-V"]):
                return []  # asks whether a command exists; nothing after it runs
            i += 1 + skip_options(words[i + 1:], WRAPPER_VALUE_OPTIONS.get(words[i], set()), WRAPPER_LONG_VALUE_OPTIONS)
        else:
            break
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

    def add(raw):
        name = host_name(raw) if raw else None
        if name and name not in found:
            found.append(name)

    for words in segments(command):
        words = strip_prefix(words)
        if not words:
            continue
        name, args = program(words[0]), words[1:]
        if name in ("ssh", "mosh", "sftp"):
            rest = args[skip_options(args, VALUE_OPTIONS[name]):]
            if rest:
                url = REMOTE_URL.match(rest[0])
                add(url.group(1) if url else rest[0].split(":", 1)[0])
        elif name in ("scp", "rsync"):
            for arg in args[skip_options(args, VALUE_OPTIONS[name]):]:
                url = REMOTE_URL.match(arg)
                path = None if url or arg.startswith(("-", "/", ".", "~")) else REMOTE_PATH.match(arg)
                if url:
                    add(url.group(1))
                elif path and len(path.group(1)) > 1:  # a single letter is a Windows drive
                    add(path.group(1))
    return found


def host_facts(host, seconds):
    """What project-memory recorded about this host, or None when there is nothing to read."""
    store = Path(os.path.expanduser("~")) / ".tstack" / "hosts" / host / "learnings.jsonl"
    if not store.is_file():
        return None
    result = subprocess.run([sys.executable, str(MEMORY_SCRIPT), "load", "--host", host], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=seconds,
                            env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    text = result.stdout.strip()
    return text if result.returncode == 0 and text.startswith("# Host memory") else None


def marker(session, host):
    """Where this session records that the host's facts were shown, or None when nothing can be kept."""
    root = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not root:
        return None
    folder = Path(root) / "host-facts-shown"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / (re.sub(r"[^A-Za-z0-9_-]", "_", session or "unknown") + "--" + host + ".flag")


def forget_old(folder):
    cutoff = time.time() - 30 * 86400
    for old in folder.glob("*.flag"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass


def host_notice(command, session):
    """(notice, deny?) for the first host in the command whose facts this session has not been shown, or None."""
    deadline = time.monotonic() + LOOKUP_SECONDS  # one budget for the whole hook run, however many hosts
    for host in remote_hosts(command):
        flag = marker(session, host)
        if flag is not None and flag.exists():
            continue  # already shown: do not read the store again
        remaining = deadline - time.monotonic()
        if remaining <= 0.5:
            break
        facts = host_facts(host, remaining)
        if not facts:
            continue
        room = NOTICE_BUDGET - len(HOST_FACTS % (host, ""))
        if len(facts) > room:
            cut = HOST_FACTS_CUT % host
            facts = facts[:room - len(cut)].rsplit("\n", 1)[0] + cut
        if flag is not None:
            flag.touch()
            forget_old(flag.parent)
        return HOST_FACTS % (host, facts), flag is not None
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
