#!/usr/bin/env python3
"""Check that the tstack skills still fit together.

Usage: check_stack.py [--root PATH]

Checks, each reported as file:line - problem:
  frontmatter   name equals the folder name; description is under 1024 characters and
                contains MUST; metadata.version is a quoted semantic version
  links         every relative link points to a file that exists, and its #anchor to a
                heading in that file (links inside code are ignored)
  direction     the core does not link into a stage skill; a service skill
                (agent-delegation, project-memory) does not link to or name a stage skill
  routing table every skill is named in the core's "The Stack" table
  names         a **bold** skill-like name refers to a skill that exists
  whole stack   no fallback wording for a tstack skill that might not be installed
                (skills shipped elsewhere may stay optional)
  manifests     README lists every skill and states the right count; plugin.json,
                marketplace.json and hooks.json parse; both descriptions match

Exit 0 when nothing is wrong, 1 when a problem was found, 2 on a usage error.
Standard library only.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

CORE = "software-engineering-guidelines"
SERVICES = ("agent-delegation", "project-memory")
EXTERNAL_SKILLS = ("human-writing",)  # Named in the stack, shipped elsewhere.
FALLBACKS = (r"when it is installed", r"if (it is )?installed", r"is not installed, ", r"when installed")
LINK = re.compile(r"\]\(([^)\s]+)\)")
BOLD_NAME = re.compile(r"\*\*([a-z]+(?:-[a-z]+)*)\*\*")
SEMVER = re.compile(r'^"\d+\.\d+\.\d+"$')


def slug(heading):
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def without_code(text):
    """Blank out fenced blocks and inline code, keeping line numbers."""
    out, fenced = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append("")
        else:
            out.append("" if fenced else re.sub(r"`[^`\n]*`", "", line))
    return out


def anchors(path):
    text = path.read_text(encoding="utf-8")
    return {slug(m.group(1)) for m in re.finditer(r"^#{1,6}\s+(.*)$", "\n".join(without_code(text)), re.M)}


def frontmatter(text):
    """The fields this check needs: name, description, metadata.version (raw)."""
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return None
    block = text[4:text.index("\n---", 4)]
    fields, key = {}, None
    for line in block.split("\n"):
        top = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            fields[key] = "" if value in (">", ">-", "|", "|-") else value
        elif key and line.startswith(" "):
            nested = re.match(r"^\s+version:\s*(.*)$", line)
            if key == "metadata" and nested:
                fields["version"] = nested.group(1).strip()
            elif key != "metadata":
                fields[key] = (fields[key] + " " + line.strip()).strip()
    for name in ("name", "description"):
        value = fields.get(name, "")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            fields[name] = value[1:-1]
    return fields


def check(root):
    problems = []

    def problem(path, line, text):
        problems.append("%s:%s - %s" % (os.path.relpath(path, root), line, text))

    skills_dir = root / "skills"
    skills = sorted(p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()) if skills_dir.is_dir() else []
    if CORE not in skills:
        problem(skills_dir, 0, "the core skill %s is missing" % CORE)
    stages = [s for s in skills if s != CORE and s not in SERVICES]

    for name in skills:
        path = skills_dir / name / "SKILL.md"
        fields = frontmatter(path.read_text(encoding="utf-8"))
        if fields is None:
            problem(path, 1, "frontmatter is missing")
            continue
        if fields.get("name") != name:
            problem(path, 2, "name must equal the folder name %s" % name)
        description = fields.get("description", "")
        if len(description) >= 1024:
            problem(path, 3, "description has %d characters; the limit is under 1024" % len(description))
        if "MUST" not in description:
            problem(path, 3, "description needs at least one MUST")
        if not SEMVER.match(fields.get("version", "")):
            problem(path, 1, 'metadata.version must be a quoted semantic version such as "1.0.0"')

    documents = sorted(skills_dir.rglob("*.md")) if skills_dir.is_dir() else []
    documents += [p for p in (root / "README.md", root / "AGENTS.md") if p.is_file()]
    for path in documents:
        relative = path.relative_to(root).parts
        owner = relative[1] if relative[0] == "skills" and len(relative) > 2 else None
        for number, line in enumerate(without_code(path.read_text(encoding="utf-8")), 1):
            for target in LINK.findall(line):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target):
                    continue
                file_part, _, fragment = target.partition("#")
                destination = (path.parent / file_part).resolve() if file_part else path
                if not destination.exists():
                    problem(path, number, "link target does not exist: %s" % target)
                    continue
                if fragment and destination.suffix == ".md" and fragment not in anchors(destination):
                    problem(path, number, "no heading for #%s in %s" % (fragment, file_part or path.name))
                try:
                    into = destination.relative_to(skills_dir.resolve()).parts[0]
                except (ValueError, IndexError):
                    into = None
                if owner == CORE and into in stages:
                    problem(path, number, "core must not link into stage skill %s; name it in the routing table" % into)
                if owner in SERVICES and into in stages:
                    problem(path, number, "service must not reference stage skill %s" % into)
            if owner:
                for mentioned in BOLD_NAME.findall(line):
                    if mentioned in skills:
                        if owner in SERVICES and mentioned in stages:
                            problem(path, number, "service must not reference stage skill %s" % mentioned)
                    elif mentioned not in EXTERNAL_SKILLS and re.search(r"-(review|scan|it|fix|memory|delegation|architect|inspector|guidelines)$", mentioned):
                        problem(path, number, "unknown skill %s" % mentioned)
                names_tstack_skill = any(re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(n), line) for n in skills)
                for pattern in FALLBACKS:
                    if names_tstack_skill and re.search(pattern, line):
                        problem(path, number, "tstack is installed as a whole; remove the fallback for a missing skill")
                        break

    core_file = skills_dir / CORE / "SKILL.md"
    if core_file.is_file():
        text = core_file.read_text(encoding="utf-8")
        start = text.find("## The Stack")
        end = text.find("\n## ", start + 1) if start >= 0 else -1
        table = text[start:end if end > 0 else len(text)] if start >= 0 else ""
        if not table:
            problem(core_file, 1, 'the core has no "## The Stack" routing table')
        for name in skills:
            if name != CORE and "**%s**" % name not in table:
                problem(core_file, 1, "%s is not in the core's routing table" % name)

    readme = root / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        listed = set(re.findall(r"^\| `([a-z-]+)` \|", text, re.M))
        for name in skills:
            if name not in listed:
                problem(readme, 1, "README Skills table does not list %s" % name)
        section = text[text.find("## Skills"):]
        section = section[:section.find("\n## ", 1)] if "\n## " in section[1:] else section
        for name in sorted(set(re.findall(r"^\| `([a-z-]+)` \|", section, re.M)) - set(skills)):
            problem(readme, 1, "README Skills table lists %s, which is not a skill" % name)
        count = re.search(r"(\d+) 個 skill", text)
        if count and int(count.group(1)) != len(skills):
            problem(readme, 1, "README says %s skills; there are %d" % (count.group(1), len(skills)))

    loaded = {}
    for relative in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "hooks/hooks.json"):
        path = root / relative
        try:
            loaded[relative] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problem(path, 1, "cannot be read as JSON: %s" % exc)
    plugin, market = loaded.get(".claude-plugin/plugin.json"), loaded.get(".claude-plugin/marketplace.json")
    if plugin and market:
        entries = market.get("plugins") or [{}]
        if plugin.get("description") != entries[0].get("description"):
            problem(root / ".claude-plugin/marketplace.json", 1, "description differs from plugin.json")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(prog="check_stack.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                        help="repository root to check; defaults to the repository this script is in")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error("not a directory: %s" % root)
    problems = check(root)
    for line in problems:
        print(line)
    print("%d problem(s) found." % len(problems) if problems else "tstack is consistent.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
