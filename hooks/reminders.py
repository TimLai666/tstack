#!/usr/bin/env python3
"""Optional reminders that point Claude Code to the tstack skills.

Usage: reminders.py MODE, with the hook event JSON on stdin.
Modes: session-start, pre-agent, post-agent, post-bash, pre-compact.
Any error prints nothing and exits 0, so the reminders never block work.
"""
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time

DELEGATION = "agent-delegation"

SESSION_START = (
    "這個環境裝了 tstack plugin。開始工作前，先依 project-memory skill 載入本專案的記憶。"
    "規劃、寫程式、改程式、審查或 commit 前，先載入 software-engineering-guidelines skill。"
    "要開 subagent、外派其他 CLI、變更既有 API，或交付規格、文章、報告前，先載入 agent-delegation skill。")
DENY_AGENT = (
    "這次對話還沒載入 agent-delegation skill。先載入它，依它決定這項工作由哪個工具和模型執行，"
    "再重新派工。這個提醒每個 session 只擋一次。")
AFTER_AGENT = "subagent 已回報。依 project-memory skill 核對它回報的試錯經驗與證據，符合記錄標準的經驗查證後寫入。"
AFTER_COMMIT = "已完成 commit。依 project-memory skill 檢查這段工作有沒有反覆試錯或花大量時間才找到的做法，符合記錄標準就寫入。"
BEFORE_COMPACT = "摘要時保留本 session 還沒寫入 project-memory 的試錯經驗，包括觸發情境、失敗做法、有效做法與驗證證據。"


def context(event, text):
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def delegation_loaded(transcript):
    """True when the delegation skill was loaded after the last compaction."""
    loaded = False
    try:
        with open(transcript, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if "compact_boundary" in line:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if record.get("type") == "system" and record.get("subtype") == "compact_boundary":
                        loaded = False
                elif '"Skill"' in line and DELEGATION in line:
                    try:
                        content = json.loads(line).get("message", {}).get("content")
                    except ValueError:
                        continue
                    for block in content if isinstance(content, list) else []:
                        name = str((block.get("input") or {}).get("skill", "")) if isinstance(block, dict) else ""
                        if block.get("type") == "tool_use" and block.get("name") == "Skill" and \
                                name.split(":")[-1] == DELEGATION:
                            loaded = True
    except (OSError, TypeError):
        return False
    return loaded


def remind_once(session):
    """Record the single denial for this session. False when no state can be kept."""
    root = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not root:
        return False
    folder = Path(root) / "delegation-reminded"
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / (re.sub(r"[^A-Za-z0-9_-]", "_", session or "unknown") + ".flag")
    if marker.exists():
        return None
    marker.touch()
    cutoff = time.time() - 30 * 86400
    for old in folder.glob("*.flag"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass
    return True


def is_commit(command):
    for segment in re.split(r"&&|\|\||[;|\n]", command or ""):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        if not tokens or tokens[0] != "git":
            continue
        i = 1
        while i < len(tokens) and tokens[i].startswith("-"):
            i += 2 if tokens[i] in ("-C", "-c") else 1
        if i < len(tokens) and tokens[i] == "commit" and "--dry-run" not in tokens:
            return True
    return False


def respond(mode, event):
    if mode == "session-start":
        return context("SessionStart", SESSION_START)
    if mode == "pre-compact":
        return BEFORE_COMPACT
    if event.get("agent_id"):
        return None  # Delegated subagents follow their task prompt, not these skills.
    if mode == "pre-agent":
        if delegation_loaded(event.get("transcript_path")):
            return None
        first = remind_once(event.get("session_id"))
        if first is None:
            return None
        if first is False:
            return context("PreToolUse", DENY_AGENT)
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": DENY_AGENT}}
    if mode == "post-agent":
        return context("PostToolUse", AFTER_AGENT)
    if mode == "post-bash" and is_commit((event.get("tool_input") or {}).get("command")):
        return context("PostToolUse", AFTER_COMMIT)
    return None


def main():
    try:
        event = json.loads(sys.stdin.read())
        if not isinstance(event, dict):
            return 0
        reply = respond(sys.argv[1] if len(sys.argv) > 1 else "", event)
    except Exception:  # Reminders are optional; never interrupt the session.
        return 0
    # Claude Code reads hook output as UTF-8; Windows consoles default to a legacy code page.
    if isinstance(reply, str):
        sys.stdout.buffer.write(reply.encode("utf-8") + b"\n")
    elif reply:
        sys.stdout.buffer.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
