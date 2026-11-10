#!/usr/bin/env python3
"""Stop a handful of shell commands that keep causing damage, and say what to run instead.

Usage: guard.py, with the PreToolUse hook event JSON on stdin.
A matching command is denied with the replacement in the reason. Anything this
script cannot parse is let through, and any error prints nothing and exits 0.
Set TSTACK_GUARD=off in the environment Claude Code starts from to switch it off.
"""
import json
import os
import re
import shlex
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
MERGE = ("`glab mr merge` 預設開啟 auto-merge，還沒有 pipeline 時會直接合併。"
         "先讀 MR 目前的 head commit SHA，確認該 SHA 的 pipeline 是 success，"
         "再執行 `glab mr merge <編號> --sha <SHA> --auto-merge=false --yes`。pipeline 不存在、執行中或失敗都不合併。")
KILL_BY_NAME = ("不依程式名稱結束程序，同名的程序可能是使用者或其他流程開的。"
                "只結束自己啟動的那一個：POSIX 用 `kill <PID>`，Windows 用 `taskkill /PID <PID>` 或 `Stop-Process -Id <PID>`。")
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
            if not pinned or "--auto-merge=false" not in lowered:
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
        reason = violation((event.get("tool_input") or {}).get("command"))
    except Exception:  # A guard that crashes must not block work.
        return 0
    if reason:
        reply = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                        "permissionDecisionReason": "tstack guard：" + reason}}
        # Claude Code reads hook output as UTF-8; Windows consoles default to a legacy code page.
        sys.stdout.buffer.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
