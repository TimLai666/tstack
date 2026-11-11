#!/usr/bin/env python3
"""Move a project's engineering documents from older layouts into engineering/.

Usage: migrate_layout.py [--root PATH] [--move SOURCE=DESTINATION ...] [--apply]

Without --apply nothing is changed: the script prints what it would move, what
blocks a move, what is left to do by hand, and which files still mention an old
path.

Moves:
  ENG.md                                 -> engineering/architecture.md
  docs/tickets/, docs/dev/tickets/       -> engineering/tickets/
  docs/dev/specs/                        -> engineering/specs/
  delivery-plan.md, delivery-status.md   -> engineering/reports/legacy-status.md
  HANDOFF.md                             -> engineering/handoff.md
  DESIGN-REVIEW.md, docs/dev/ui-review.md
                                         -> engineering/reports/legacy-ui-review.md
  docs/security-scan/report.md, docs/dev/security-scan.md
                                         -> engineering/reports/legacy-security-scan.md
  docs/software-engineering-guidelines/  -> engineering/reports/

Other engineering documents, chosen by the user:
  --move SOURCE=DESTINATION moves one more file or directory. SOURCE is a path
  in the project, usually under docs/; DESTINATION is a path under engineering/.
  Repeat the option for each one, for example
    --move docs/spec=engineering/specs --move docs/research=engineering/research
  Without --apply the report lists the directories under docs/ that no move
  covers, so that the user can say which of them hold engineering documents.
  A directory moved to engineering/tickets is filed like the other tickets.

Tickets are filed by their old status field, and the field is removed, because
the directory a ticket is in is now its state:
  done, completed, closed, merged        -> engineering/tickets/done/
  in progress, doing, wip, active        -> engineering/tickets/doing/
  ready, open, todo, not started, ...    -> engineering/tickets/
  blocked, with tickets under Blocked by  -> stays open; the field is removed
  blocked, with nothing under Blocked by -> stays open; the line becomes **Blocked:**
A ticket whose status value is not recognized keeps the line and is reported.
Tickets already in engineering/tickets/ that still carry a status field are
filed the same way.

Rules:
  - delivery-plan.md is moved only when it reads as a status record (it has a
    "Next Verifiable Output", "Next Ticket" or "Next OpenSpec Change" heading).
    A feature plan stays.
  - PLAN.md and TODOS.md at the root are reported and never moved: the oldest
    versions of this workflow wrote them, and so do people.
  - A move is blocked, and reported, when its destination exists or when two
    sources share one destination. Nothing is overwritten or deleted.
  - Tracked files move with `git mv`; other files are renamed.
  - A source directory is removed only when the move left it empty.
  - Links inside a moved Markdown file are rewritten so that they survive this
    move and later moves between ticket directories: a link from one ticket to
    another becomes its link text, and any other relative link becomes a path
    from the repository root.
  - The status field may be written **Status:** or Status:, in English or as 狀態.
  - The files under engineering/reports/legacy-* hold content that has no place
    in the new layout as it stands. The script lists what to carry over by hand.
  - A link in any other Markdown file that pointed at a moved file is updated
    to the new location. A mention of an old path in prose is listed, not edited.

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
    ("HANDOFF.md", "engineering/handoff.md"),
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
    "engineering/reports/legacy-status.md": "write each Decision Log entry that still holds as a decision record, move "
                                            "each handoff note to the ticket it concerns or to engineering/handoff.md, state the order between "
                                            "OpenSpec changes in their proposals, then delete the file",
    "engineering/handoff.md": "keep only unfinished work that has no ticket; move each other note to the ticket it "
                              "concerns, each working rule to AGENTS.md and each fact about a machine to project memory",
    "engineering/reports/legacy-ui-review.md": "write each open item as a fix ticket and each component's copy and states "
                                               "into that feature's specification, then delete the file",
    "engineering/reports/legacy-security-scan.md": "write each unfixed finding as a fix ticket, after the user confirms "
                                                   "when the repository is public, then delete the file",
}
STATUS_HEADING = re.compile(r"^#+\s*`?(Next Verifiable Output|Next Ticket|Next OpenSpec Change)`?\s*$", re.MULTILINE)
UNDECIDED = {
    "PLAN.md": "if an earlier version of this workflow wrote it, carry its scope into a specification",
    "TODOS.md": "if an earlier version of this workflow wrote it, turn each open item into a ticket",
}
STATUS_LINE = re.compile(r"^(?:\*\*)?(?:Status|狀態)[:：]?(?:\*\*)?[:：]?[ \t]*(.*?)[ \t]*\r?\n", re.MULTILINE | re.IGNORECASE)
DONE = {"done", "complete", "completed", "closed", "merged", "finished", "shipped", "完成", "已完成"}
DOING = {"in progress", "doing", "wip", "active", "started", "in review", "進行中"}
OPEN = {"ready", "open", "todo", "to do", "not started", "pending", "backlog", "new", "planned", "待辦", "未開始", "就緒"}
BLOCKED_BY = re.compile(r"^(?:\*\*)?Blocked by[:：]?(?:\*\*)?[:：]?[ \t]*(.*)$", re.MULTILINE | re.IGNORECASE)
NO_BLOCKER = re.compile(r"^[\s`*]*(none|n/?a|無|—|-|)[\s`*.]*$", re.IGNORECASE)
LINK = re.compile(r"(!?)\[([^\]\n]*)\]\(([^)\s]+)\)")
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
    text = read(path)
    match = STATUS_LINE.search(text)
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
        blockers = BLOCKED_BY.search(text)
        if blockers and not NO_BLOCKER.match(blockers.group(1)):
            return "", "strip", None
        return "", "blocked", "its status was blocked; say on the **Blocked:** line what it waits for"
    return "", None, f"status '{match.group(1)}' is not recognized; file it by hand and remove the line"


def plan(root, extra=()):
    """Return (moves, blocked, notes); a move is (source, destination, edit)."""
    candidates, notes = [], []
    directories = list(DIRECTORIES)
    ticket_directories = list(TICKET_DIRECTORIES)
    for source, destination in extra:
        if (root / source).is_file():
            candidates.append((source, destination, None))
        elif destination == TICKETS:
            ticket_directories.append(source)
        else:
            directories.append((source, destination))
    for source, destination in FILES:
        if not (root / source).is_file():
            continue
        if source == "delivery-plan.md" and not STATUS_HEADING.search(read(root / source)):
            notes.append(f"{source}: does not read as a status record, left in place")
            continue
        candidates.append((source, destination, None))
    for name, task in UNDECIDED.items():
        if (root / name).is_file():
            notes.append(f"{name}: not moved; {task}, then ask the user before deleting it")
    for source, destination in directories:
        for item in sorted((root / source).rglob("*")) if (root / source).is_dir() else []:
            if item.is_file():
                relative = item.relative_to(root / source).as_posix()
                candidates.append((f"{source}/{relative}", f"{destination}/{relative}", None))
    ticket_files = []
    for source in ticket_directories:
        for item in sorted((root / source).rglob("*")) if (root / source).is_dir() else []:
            if item.is_file():
                relative = item.relative_to(root / source).as_posix()
                ticket_files.append((f"{source}/{relative}", relative))
    if (root / TICKETS).is_dir():
        for item in sorted((root / TICKETS).glob("*.md")):
            if item.name.lower() != "readme.md" and STATUS_LINE.search(read(item)):
                ticket_files.append((f"{TICKETS}/{item.name}", item.name))
    for source, relative in ticket_files:
        name = relative.rsplit("/", 1)[-1]
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


def is_ticket(path):
    return (path.startswith(TICKETS + "/") and path.lower().endswith((".md", ".mdx"))
            and not path.lower().endswith("readme.md"))


def relink(root, text, source, destination, moved, only_moved=False):
    """Rewrite the relative links of a file that moved from source to destination.

    With only_moved, the file itself stayed put and only its links to moved files change.
    """
    def replace(match):
        image, label, target = match.groups()
        path, _, anchor = target.partition("#")
        if not path or path.startswith(("/", "#")) or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", path):
            return match.group(0)
        old = os.path.normpath(os.path.join(os.path.dirname(source), path)).replace(os.sep, "/")
        if old.startswith(".."):
            return match.group(0)
        new = moved.get(old, old)
        if not (root / new).exists() or (only_moved and old not in moved):
            return match.group(0)
        if not image and is_ticket(destination) and is_ticket(new):
            return label
        return f"{image}[{label}](/{new}{'#' + anchor if anchor else ''})"
    return LINK.sub(replace, text)


def apply(root, moves):
    moved = {source: destination for source, destination, _ in moves}
    for source, destination, edit in moves:
        if source != destination:
            (root / destination).parent.mkdir(parents=True, exist_ok=True)
            if is_tracked(root, source):
                subprocess.run(["git", "mv", "--", source, destination], cwd=root, check=True,
                               capture_output=True, text=True)
            else:
                os.rename(root / source, root / destination)
    for source, destination, edit in moves:
        path = root / destination
        if not destination.lower().endswith((".md", ".mdx")):
            continue
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        changed = text
        if edit:
            replacement = "" if edit == "strip" else "**Blocked:** reason not recorded\n"
            changed = STATUS_LINE.sub(replacement, changed, count=1)
        changed = relink(root, changed, source, destination, moved)
        if changed != text:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(changed)
    arrived = set(moved.values())
    for folder, names, files in os.walk(root):
        names[:] = [n for n in names if n not in SKIPPED_DIRECTORIES]
        for name in files:
            relative = (Path(folder) / name).relative_to(root).as_posix()
            if relative in arrived or not name.lower().endswith((".md", ".mdx")):
                continue
            try:
                with open(Path(folder) / name, encoding="utf-8", newline="") as handle:
                    text = handle.read()
            except (OSError, UnicodeDecodeError):
                continue
            changed = relink(root, text, relative, relative, moved, only_moved=True)
            if changed != text:
                with open(Path(folder) / name, "w", encoding="utf-8", newline="") as handle:
                    handle.write(changed)
    emptied = {str(Path(source).parent) for source, destination, _ in moves if source != destination}
    for folder in sorted(emptied, key=len, reverse=True):
        current = root / folder
        while current != root and current.is_dir() and not any(current.iterdir()):
            current.rmdir()
            current = current.parent


def references(root, extra=()):
    """Lines in Markdown files that still mention an old path."""
    found = []
    custom = [source + ("/" if (root / destination).is_dir() else "") for source, destination in extra
              if (root / destination).exists() and not (root / source).exists()]
    for folder, names, files in os.walk(root):
        names[:] = [n for n in names if n not in SKIPPED_DIRECTORIES]
        for name in files:
            if not name.lower().endswith((".md", ".mdx")):
                continue
            path = Path(folder) / name
            for number, line in enumerate(read(path).splitlines(), 1):
                if OLD_PATH.search(line) or any(path in line for path in custom):
                    found.append(f"{path.relative_to(root).as_posix()}:{number}: {line.strip()[:160]}")
    return found


def describe(source, destination, edit):
    if source == destination:
        return f"{source}: status field {'removed' if edit == 'strip' else 'turned into **Blocked:**'}"
    suffix = {"strip": " (status field removed)", "blocked": " (status field turned into **Blocked:**)"}.get(edit, "")
    return f"{source} -> {destination}{suffix}"


def parse_moves(parser, root, values):
    moves = []
    for value in values or []:
        source, separator, destination = value.partition("=")
        source, destination = source.strip().strip("/"), destination.strip().strip("/")
        if not separator or not source or not destination:
            parser.error(f"--move takes SOURCE=DESTINATION, got: {value}")
        if os.path.isabs(source) or ".." in Path(source).parts or ".." in Path(destination).parts:
            parser.error(f"--move paths stay inside the project: {value}")
        if not destination.startswith("engineering/"):
            parser.error(f"--move destination has to be under engineering/: {value}")
        if source == "engineering" or source.startswith("engineering/"):
            parser.error(f"--move source is already under engineering/: {value}")
        if not (root / source).exists() and not (root / destination).exists():
            parser.error(f"--move source does not exist: {source}")
        moves.append((source, destination))
    return moves


def uncovered_docs(root, extra):
    """Directories directly under docs/ that no move covers, with their file counts."""
    covered = [source for source, _ in list(DIRECTORIES) + list(extra)] + TICKET_DIRECTORIES + ["docs/security-scan"]
    found = []
    for item in sorted((root / "docs").iterdir()) if (root / "docs").is_dir() else []:
        path = f"docs/{item.name}"
        if not item.is_dir() or any(c == path or c.startswith(path + "/") or path.startswith(c + "/") for c in covered):
            continue
        found.append((path, sum(1 for f in item.rglob("*") if f.is_file())))
    return found


def main():
    parser = argparse.ArgumentParser(prog="migrate_layout.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--move", action="append", metavar="SOURCE=DESTINATION",
                        help="also move this file or directory to a path under engineering/; repeatable")
    parser.add_argument("--apply", action="store_true", help="carry out the moves; without it only report")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    extra = parse_moves(parser, root, args.move)
    moves, blocked, notes = plan(root, extra)
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
               if path in arriving or (path.startswith("engineering/reports/") and (root / path).exists())]
    if by_hand:
        print("Carry over by hand:")
        for path, task in by_hand:
            print(f"  {path}: {task}")
    mentions = references(root, extra)
    if mentions:
        print("Still mention an old path; update each to the new path:")
        for line in mentions:
            print(f"  {line}")
    index_files = [d for _, d, _ in moves if d.startswith(TICKETS + "/") and not is_ticket(d)]
    if index_files:
        print("Moved with the tickets; remove any copy of ticket state they hold, or regenerate them:")
        for path in index_files:
            print(f"  {path}")
    if (moves or (root / "engineering").is_dir()) and not (root / "engineering" / "README.md").exists():
        print("engineering/README.md is missing; write it before finishing.")
    others = [] if args.apply else uncovered_docs(root, extra)
    if others:
        print("Other directories under docs/; for each one that holds engineering documents, add --move SOURCE=engineering/NAME:")
        for path, count in others:
            print(f"  {path}/ ({count} files)")
    if not args.apply and moves:
        print("Run again with --apply to carry out the moves.")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
