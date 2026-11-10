#!/usr/bin/env python3
"""Reminders that point Claude Code to the tstack skills, and the project memory at session start.

Usage: reminders.py MODE, with the hook event JSON on stdin.
Modes: session-start, pre-agent, post-agent, post-bash, pre-compact.
Any error prints nothing and exits 0, so the reminders never block work.
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

DELEGATION = "agent-delegation"

MEMORY_SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "project-memory" / "scripts" / "memory.py"
# Claude Code replaces hook context over 10,000 characters with a short preview.
CONTEXT_BUDGET = 9000

INTRO = "The tstack plugin is installed in this environment."
MEMORY_LOADED = ("Below are this project's memory, the user's global preferences and this machine's facts, already loaded by project-memory; "
                 "no need to run load again in this conversation. To read the full text of an entry, use search:\n\n")
MEMORY_EMPTY = "This project has no memory yet in project-memory, and there are no global preferences or facts about this machine yet."
MEMORY_KEYS = ("The memory is too long for the hook to include in full, so some entries below show only their keys. "
               "Before starting work, run load as the project-memory skill describes to read all of it:\n\n")
MEMORY_UNREAD = "Before starting work, load this project's memory as the project-memory skill describes."
SKILLS = ("\n\nBefore planning, writing or changing code, reviewing or committing, load the software-engineering-guidelines skill. "
          "Before opening a subagent, dispatching another CLI, changing an existing API, or delivering specifications, articles or reports, load the agent-delegation skill.")
DENY_AGENT = (
    "This conversation has not loaded the agent-delegation skill yet. Load it first, let it decide which tool and model does this work, "
    "then dispatch again. This notice blocks only once per session.")
AFTER_AGENT = "The subagent reported back. Check the trial-and-error lessons and evidence it reported against the project-memory skill, and after verifying the ones that meet the recording standard, write them in."
AFTER_COMMIT = "The commit is done. Use the project-memory skill to check whether this work involved repeated trial and error or a solution that took a lot of time to find, and record it if it meets the standard."
BEFORE_COMPACT = "When summarizing, keep the trial-and-error lessons from this session that are not yet written to project-memory, including the trigger, the failed approach, the effective approach and the verification evidence."


def context(event, text):
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def run_memory(cwd, *args):
    """Output of the project-memory script for the project in cwd, or None when it fails."""
    result = subprocess.run([sys.executable, str(MEMORY_SCRIPT), *args], cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=8,
                            env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    return result.stdout.strip() if result.returncode == 0 else None


def session_start(cwd):
    """The session-start context: the project's memory when it fits, otherwise how to get it."""
    try:
        if not cwd or not os.path.isdir(cwd):
            raise OSError("no project directory")
        room = CONTEXT_BUDGET - len(INTRO + SKILLS) - max(len(MEMORY_LOADED), len(MEMORY_KEYS))
        # One call only: the script trims its own output, so a busy machine cannot push the hook past its time limit.
        loaded = run_memory(cwd, "load", "--fit", str(room))
        if loaded is None:
            raise OSError("memory script failed")
        if loaded.startswith("NO_LEARNINGS") and "\n# " not in loaded:  # no global, machine or host section either
            memory = MEMORY_EMPTY
        elif any(line.startswith("# ") and "keys only:" in line for line in loaded.split("\n")):
            memory = MEMORY_KEYS + loaded
        else:
            memory = MEMORY_LOADED + loaded
    except Exception:  # Fall back to asking for the load; never leave the session without the reminder.
        memory = MEMORY_UNREAD
    return INTRO + memory + SKILLS


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
        return context("SessionStart", session_start(event.get("cwd")))
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
