#!/usr/bin/env python3
"""Move a project's engineering documents from older layouts into engineering/.

Usage: migrate_layout.py [--root PATH] [--apply]

Without --apply nothing is changed: the script prints what it would move, what
blocks a move, and which files still mention an old path.

Moves, oldest layout first:
  delivery-plan.md                       -> engineering/status.md
  delivery-status.md                     -> engineering/status.md
  ENG.md                                 -> engineering/architecture.md
  DESIGN-REVIEW.md                       -> engineering/reviews/ui.md
  docs/dev/ui-review.md                  -> engineering/reviews/ui.md
  docs/security-scan/report.md           -> engineering/reviews/security.md
  docs/dev/security-scan.md              -> engineering/reviews/security.md
  docs/tickets/, docs/dev/tickets/       -> engineering/tickets/
  docs/dev/specs/                        -> engineering/specs/
  docs/software-engineering-guidelines/  -> engineering/tasks/

Rules:
  - delivery-plan.md is moved only when it reads as a status record (it has a
    "Next Verifiable Output" or "Next Ticket" heading). A feature plan stays.
  - A move is blocked, and reported, when its destination exists or when two
    sources share one destination. Nothing is overwritten or deleted.
  - Tracked files move with `git mv`; other files are renamed.
  - A source directory is removed only when the move left it empty.
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
    ("delivery-plan.md", "engineering/status.md"),
    ("delivery-status.md", "engineering/status.md"),
    ("ENG.md", "engineering/architecture.md"),
    ("DESIGN-REVIEW.md", "engineering/reviews/ui.md"),
    ("docs/dev/ui-review.md", "engineering/reviews/ui.md"),
    ("docs/security-scan/report.md", "engineering/reviews/security.md"),
    ("docs/dev/security-scan.md", "engineering/reviews/security.md"),
]
DIRECTORIES = [
    ("docs/tickets", "engineering/tickets"),
    ("docs/dev/tickets", "engineering/tickets"),
    ("docs/dev/specs", "engineering/specs"),
    ("docs/software-engineering-guidelines", "engineering/tasks"),
]
STATUS_HEADING = re.compile(r"^#+\s*`?(Next Verifiable Output|Next Ticket)`?\s*$", re.MULTILINE)
OLD_PATH = re.compile(
    r"(?<![\w/.-])(delivery-plan\.md|delivery-status\.md|ENG\.md|DESIGN-REVIEW\.md)(?![\w-])"
    r"|docs/(?:tickets|dev|security-scan|software-engineering-guidelines)/")
SKIPPED_DIRECTORIES = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv"}


def is_status_record(path):
    try:
        return bool(STATUS_HEADING.search(path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def plan(root):
    """Return (moves, blocked, notes); moves are (source, destination) relative paths."""
    candidates, notes = [], []
    for source, destination in FILES:
        if not (root / source).is_file():
            continue
        if source == "delivery-plan.md" and not is_status_record(root / source):
            notes.append(f"{source}: does not read as a status record, left in place")
            continue
        candidates.append((source, destination))
    for source, destination in DIRECTORIES:
        if not (root / source).is_dir():
            continue
        for item in sorted((root / source).rglob("*")):
            if item.is_file():
                relative = item.relative_to(root / source).as_posix()
                candidates.append((f"{source}/{relative}", f"{destination}/{relative}"))
    by_destination = {}
    for source, destination in candidates:
        by_destination.setdefault(destination, []).append(source)
    moves, blocked = [], []
    for source, destination in candidates:
        rivals = by_destination[destination]
        if (root / destination).exists():
            blocked.append(f"{source}: {destination} already exists; compare the two and merge by hand")
        elif len(rivals) > 1:
            others = ", ".join(r for r in rivals if r != source)
            blocked.append(f"{source}: {others} has the same destination {destination}; decide which one is current")
        else:
            moves.append((source, destination))
    return moves, blocked, notes


def is_tracked(root, path):
    result = subprocess.run(["git", "ls-files", "--error-unmatch", "--", path], cwd=root,
                            capture_output=True, text=True)
    return result.returncode == 0


def apply(root, moves):
    for source, destination in moves:
        (root / destination).parent.mkdir(parents=True, exist_ok=True)
        if is_tracked(root, source):
            subprocess.run(["git", "mv", "--", source, destination], cwd=root, check=True,
                           capture_output=True, text=True)
        else:
            os.rename(root / source, root / destination)
    emptied = {str(Path(source).parent) for source, _ in moves}
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
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, 1):
                if OLD_PATH.search(line):
                    found.append(f"{path.relative_to(root).as_posix()}:{number}: {line.strip()[:160]}")
    return found


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
    verb = "Moved" if args.apply else "Would move"
    if moves:
        print(f"{verb}:")
        for source, destination in moves:
            print(f"  {source} -> {destination}")
    else:
        print("Nothing to move.")
    if blocked:
        print("Blocked, nothing changed for these:")
        for line in blocked:
            print(f"  {line}")
    for line in notes:
        print(f"Note: {line}")
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
