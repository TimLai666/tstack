#!/usr/bin/env python3
"""Move a project's engineering documents from older layouts into engineering/.

Usage: migrate_layout.py [--root PATH] [--apply]

Without --apply nothing is changed: the script prints what it would move, what
blocks a move, what is left to do by hand, and which files still mention an old
path.

Moves:
  ENG.md                                 -> engineering/architecture.md
  docs/tickets/, docs/dev/tickets/       -> engineering/tickets/
  docs/dev/specs/                        -> engineering/specs/
  delivery-plan.md, delivery-status.md   -> engineering/reports/legacy-status.md
  DESIGN-REVIEW.md, docs/dev/ui-review.md
                                         -> engineering/reports/legacy-ui-review.md
  docs/security-scan/report.md, docs/dev/security-scan.md
                                         -> engineering/reports/legacy-security-scan.md
  docs/software-engineering-guidelines/  -> engineering/reports/

Tickets are filed by their old status field, and the field is removed, because
the directory a ticket is in is now its state:
  done, completed, closed, merged        -> engineering/tickets/done/
  in progress, doing, wip, active        -> engineering/tickets/doing/
  ready, open, todo, not started, ...    -> engineering/tickets/
  blocked                                -> stays open; the line becomes **Blocked:**
A ticket whose status value is not recognized keeps the line and is reported.
Tickets already in engineering/tickets/ that still carry a status field are
filed the same way.

Rules:
  - delivery-plan.md is moved only when it reads as a status record (it has a
    "Next Verifiable Output" or "Next Ticket" heading). A feature plan stays.
  - A move is blocked, and reported, when its destination exists or when two
    sources share one destination. Nothing is overwritten or deleted.
  - Tracked files move with `git mv`; other files are renamed.
  - A source directory is removed only when the move left it empty.
  - The status field may be written **Status:** or Status:, in English or as 狀態.
  - The files under engineering/reports/legacy-* hold content that has no place
    in the new layout as it stands. The script lists what to carry over by hand.
  - References to old paths in Markdown files are listed, not edited.

Exit status: 0 when nothing is blocked, 1 when a move is blocked, 2 on a usage
error.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

FILES = [
    ("ENG.md", "engineering/architecture.md"),
    ("delivery-plan.md", "engineering/reports/legacy-status.md"),
    ("delivery-status.md", "engineering/reports/legacy-status.md"),
    ("DESIGN-REVIEW.md", "engineering/reports/legacy-ui-review.md"),
    ("docs/dev/ui-review.md", "engineering/reports/legacy-ui-review.md"),
    ("docs/security-scan/report.md", "engineering/reports/legacy-security-scan.md"),
    ("docs/dev/security-scan.md", "engineering/reports/legacy-security-scan.md"),
]
DIRECTORIES = [
    ("docs/dev/specs", "engineering/specs"),
    ("docs/software-engineering-guidelines", "engineering/reports"),
]
TICKET_DIRECTORIES = ["docs/tickets", "docs/dev/tickets"]
TICKETS = "engineering/tickets"
BY_HAND = {
    "engineering/architecture.md": "keep the system as it is now; move the reasoning of each hard-to-reverse choice "
                                   "to a decision record and the migration steps of one change to its ticket",
    "engineering/reports/legacy-status.md": "write each Decision Log entry that still holds as a decision record, check "
                                            "that every blocker is on its ticket, then delete the file",
    "engineering/reports/legacy-ui-review.md": "write each open item as a fix ticket and each component's copy and states "
                                               "into that feature's specification, then delete the file",
    "engineering/reports/legacy-security-scan.md": "write each unfixed finding as a fix ticket, after the user confirms "
                                                   "when the repository is public, then delete the file",
}
STATUS_HEADING = re.compile(r"^#+\s*`?(Next Verifiable Output|Next Ticket)`?\s*$", re.MULTILINE)
STATUS_LINE = re.compile(r"^(?:\*\*)?(?:Status|狀態)[:：]?(?:\*\*)?[:：]?[ \t]*(.*?)[ \t]*\r?\n", re.MULTILINE | re.IGNORECASE)
DONE = {"done", "complete", "completed", "closed", "merged", "finished", "shipped", "完成", "已完成"}
DOING = {"in progress", "doing", "wip", "active", "started", "in review", "進行中"}
OPEN = {"ready", "open", "todo", "to do", "not started", "pending", "backlog", "new", "planned", "待辦", "未開始", "就緒"}
OLD_PATH = re.compile(
    r"(?<![\w/.-])(delivery-plan\.md|delivery-status\.md|ENG\.md|DESIGN-REVIEW\.md)(?![\w-])"
    r"|docs/(?:tickets|dev|security-scan|software-engineering-guidelines)/")
SKIPPED_DIRECTORIES = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv"}


def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def ticket_state(path):
    """Return (subdirectory, edit, note) from a ticket's old status field."""
    match = STATUS_LINE.search(read(path))
    if not match:
        return "", None, None
    value = re.sub(r"[_\-]+", " ", match.group(1).strip("`* ").lower())
    if value in DONE:
        return "done", "strip", None
    if value in DOING:
        return "doing", "strip", None
    if value in OPEN:
        return "", "strip", None
    if value.startswith(("blocked", "卡住", "阻塞")):
        return "", "blocked", "its status was blocked; say on the **Blocked:** line what it waits for"
    return "", None, f"status '{match.group(1)}' is not recognized; file it by hand and remove the line"


def plan(root):
    """Return (moves, blocked, notes); a move is (source, destination, edit)."""
    candidates, notes = [], []
    for source, destination in FILES:
        if not (root / source).is_file():
            continue
        if source == "delivery-plan.md" and not STATUS_HEADING.search(read(root / source)):
            notes.append(f"{source}: does not read as a status record, left in place")
            continue
        candidates.append((source, destination, None))
    for source, destination in DIRECTORIES:
        for item in sorted((root / source).rglob("*")) if (root / source).is_dir() else []:
            if item.is_file():
                relative = item.relative_to(root / source).as_posix()
                candidates.append((f"{source}/{relative}", f"{destination}/{relative}", None))
    ticket_files = []
    for source in TICKET_DIRECTORIES:
        for item in sorted((root / source).rglob("*")) if (root / source).is_dir() else []:
            if item.is_file():
                ticket_files.append((f"{source}/{item.relative_to(root / source).as_posix()}", item.name))
    if (root / TICKETS).is_dir():
        for item in sorted((root / TICKETS).glob("*.md")):
            if item.name.lower() != "readme.md" and STATUS_LINE.search(read(item)):
                ticket_files.append((f"{TICKETS}/{item.name}", item.name))
    for source, name in ticket_files:
        relative = source.split("/tickets/", 1)[1]
        if not name.lower().endswith((".md", ".mdx")) or name.lower() == "readme.md":
            candidates.append((source, f"{TICKETS}/{relative}", None))
            continue
        subdirectory, edit, note = ticket_state(root / source)
        parts = [TICKETS] + ([subdirectory] if subdirectory else []) + [relative]
        candidates.append((source, "/".join(parts), edit))
        if note:
            notes.append(f"{source}: {note}")
    by_destination = {}
    for source, destination, _ in candidates:
        by_destination.setdefault(destination, []).append(source)
    moves, blocked = [], []
    for source, destination, edit in candidates:
        rivals = by_destination[destination]
        if source == destination:
            if edit:
                moves.append((source, destination, edit))
        elif (root / destination).exists():
            blocked.append(f"{source}: {destination} already exists; compare the two and merge by hand")
        elif len(rivals) > 1:
            others = ", ".join(r for r in rivals if r != source)
            blocked.append(f"{source}: {others} has the same destination {destination}; decide which one is current")
        else:
            moves.append((source, destination, edit))
    return moves, blocked, notes


def is_tracked(root, path):
    result = subprocess.run(["git", "ls-files", "--error-unmatch", "--", path], cwd=root,
                            capture_output=True, text=True)
    return result.returncode == 0


def apply(root, moves):
    for source, destination, edit in moves:
        if source != destination:
            (root / destination).parent.mkdir(parents=True, exist_ok=True)
            if is_tracked(root, source):
                subprocess.run(["git", "mv", "--", source, destination], cwd=root, check=True,
                               capture_output=True, text=True)
            else:
                os.rename(root / source, root / destination)
        if edit:
            path = root / destination
            text = path.read_text(encoding="utf-8")
            replacement = "" if edit == "strip" else "**Blocked:** reason not recorded\n"
            path.write_text(STATUS_LINE.sub(replacement, text, count=1), encoding="utf-8", newline="")
    emptied = {str(Path(source).parent) for source, destination, _ in moves if source != destination}
    for folder in sorted(emptied, key=len, reverse=True):
        current = root / folder
        while current != root and current.is_dir() and not any(current.iterdir()):
            current.rmdir()
            current = current.parent


def references(root):
    """Lines in Markdown files that still mention an old path."""
    found = []
    for folder, names, files in os.walk(root):
        names[:] = [n for n in names if n not in SKIPPED_DIRECTORIES]
        for name in files:
            if not name.lower().endswith((".md", ".mdx")):
                continue
            path = Path(folder) / name
            for number, line in enumerate(read(path).splitlines(), 1):
                if OLD_PATH.search(line):
                    found.append(f"{path.relative_to(root).as_posix()}:{number}: {line.strip()[:160]}")
    return found


def describe(source, destination, edit):
    if source == destination:
        return f"{source}: status field {'removed' if edit == 'strip' else 'turned into **Blocked:**'}"
    suffix = {"strip": " (status field removed)", "blocked": " (status field turned into **Blocked:**)"}.get(edit, "")
    return f"{source} -> {destination}{suffix}"


def main():
    parser = argparse.ArgumentParser(prog="migrate_layout.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--apply", action="store_true", help="carry out the moves; without it only report")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    moves, blocked, notes = plan(root)
    if args.apply and moves:
        apply(root, moves)
    if moves:
        print("Moved:" if args.apply else "Would move:")
        for move in moves:
            print(f"  {describe(*move)}")
    else:
        print("Nothing to move.")
    if blocked:
        print("Blocked, nothing changed for these:")
        for line in blocked:
            print(f"  {line}")
    for line in notes:
        print(f"Note: {line}")
    arriving = {destination for _, destination, _ in moves}
    by_hand = [(path, task) for path, task in BY_HAND.items()
               if path != "engineering/architecture.md" and ((root / path).exists() or path in arriving)
               or path == "engineering/architecture.md" and path in arriving]
    if by_hand:
        print("Carry over by hand:")
        for path, task in by_hand:
            print(f"  {path}: {task}")
    mentions = references(root)
    if mentions:
        print("Still mention an old path; update each to the new path:")
        for line in mentions:
            print(f"  {line}")
    if (moves or (root / "engineering").is_dir()) and not (root / "engineering" / "README.md").exists():
        print("engineering/README.md is missing; write it before finishing.")
    if not args.apply and moves:
        print("Run again with --apply to carry out the moves.")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
