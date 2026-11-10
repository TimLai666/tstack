---
name: project-memory
description: "Shared cross-agent project memory for costly trial-and-error, hard-won solutions and verified corrections to outdated lessons. This skill MUST be invoked before starting work in an existing project, to load what was already learned there, and MUST be invoked again as that work wraps up, to record what this session learned before it ends. MUST also be invoked on the triggers below to record something new, and SHOULD be invoked whenever the user states something worth remembering about how this project behaves. MUST NOT be used for task lists or open bugs, which belong in the issue tracker or AGENTS.md. Triggers on: 記一下, 之前踩過什麼雷, 學到什麼, 有什麼教訓, remember this, lesson learned, project learnings, 記錄一下, 之前遇過的, 把這個記起來"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - AskUserQuestion
metadata:
  version: "1.13.0"
---

## Purpose and workflow

Keep project-specific solutions that took repeated failed attempts or substantial searching, time or tokens to find, so the next agent can avoid repeating that work.

1. **Starting work in a project** — read this project's memory before reading code or making changes, without waiting to be asked. When the session opened with the memory already in context (the tstack session-start hook provides it in Claude Code), use that and do not run `load` again. When it is absent, or only keys are listed, run `load`. Search related keys before working in that area.
2. **When something is learned or work wraps up** — check the recording criteria below and run `add` for qualifying lessons. Report saved entries; if nothing qualifies, no announcement is needed.

## The script

All reads and writes go through `scripts/memory.py` in this skill's own
directory. Do not hand-build JSON with `echo` — an insight containing a quote or
backslash silently corrupts the file.

Requires `python3` (stdlib only, no packages). If it is missing, say so rather
than falling back to shell string-building.

```bash
_MEM="<this skill's directory>/scripts/memory.py"
python3 "$_MEM" --help
```

| Command | What it does |
|---|---|
| `load` | Print this project's memory, deduplicated by key, layered |
| `load --all` | Same but every entry expanded |
| `load --json` | Same, as a JSON array |
| `add` | Append one learning, optionally merging older ones into it |
| `search QUERY` | Filter learnings by substring |
| `stats` | Counts by type and average confidence |
| `path` | Print the store path for this project |

---

## Load

```bash
python3 "$_MEM" load
```

The output is layered by where else the knowledge exists. `pitfall`, `pattern` and
`preference` print in full, because nothing else in the project writes them down.
`architecture` and `tool` print as a bare key list, because `AGENTS.md` and the
code already carry them and the agent is about to read those anyway:

```
## Only recorded here (pitfall, pattern, preference)
- **n-plus-one-products** (9/10) — Product.includes(:variants) needed in catalog controller

## Index — 42 more, run `search <key>` for the full text
- **architecture**: no-orm-raw-sql, events-are-append-only
- **tool**: rg-over-grep
```

Every key is always listed, however large the store gets. Collapsing detail is
fine; hiding that an entry exists is not — a key you cannot see is one you will
never search for. When a key looks related to what you are about to do, run
`search <key>` before you touch that area:

```bash
python3 "$_MEM" search n-plus-one-products
```

Already deduplicated: same key, newest wins. `NO_LEARNINGS` means a fresh
project; carry on. Damaged lines are skipped and reported rather than aborting.

`--all` expands everything, for when you want to read the whole store.

`load` ends with a recording reminder; `--json` and `--all` omit it.

---

## Add

Draft the fields from what actually happened and write qualifying entries without
asking the user to supply or approve each field. Report what was saved.

1. **Type** — `pitfall` for something that actually went wrong, `pattern` for a
   way of working that turned out to hold, `preference` for how the user wants
   things done. Those three load in full. `architecture` and `tool` describe how
   the project is put together and load as keys only, because a file in the repo
   already says it. Pick by which of those the entry is, not by how important it
   feels or by which one gets shown.
2. **Key** — kebab-case, and it must describe the lesson. Most entries appear in
   `load` as nothing but their key, so `lesson-001` is invisible in practice
   while `n-plus-one-products` is findable. The script rejects generic and
   numbered keys.
3. **Insight** — a concise, reusable lesson: applicable conditions, failed approaches worth avoiding, the verified solution and its evidence or location. Include the root cause when confirmed; label anything still uncertain.
4. **Confidence** — 1-10

```bash
python3 "$_MEM" add \
  --type pitfall \
  --key n-plus-one-products \
  --insight 'Product.includes(:variants) needed in catalog controller — N+1 caused 3s load' \
  --confidence 9 \
  --files 'app/controllers/catalog_controller.rb'
```

The script fills in timestamp, branch and slug. `--source` defaults to
`user-stated`; other skills should pass their own name.

Re-adding an existing key is how you update it. `load` shows only the newest. Before correcting an old lesson, follow [When an old lesson fails](#when-an-old-lesson-fails).

---

Before merging entries with the same root cause, read
[Merging entries](references/store-operations.md#merging-entries) for the command,
preservation rules and how to restore an absorbed key.

## What is worth recording

- Confidence 7 or above only.
- Project-specific lessons only. General programming knowledge does not belong here.
  Facts about the machine, its tools or the user's general preferences hold in
  every project: propose them for the user-level instruction file instead of
  saving them under one project.
- A pitfall met for the second time in this project MUST be recorded, even when
  each occurrence was cheap.
- A rule the user was promised will be remembered is written in that same turn.
  Report its key and a one-sentence summary of what was saved.
- Would the line be at home in `AGENTS.md`? Then write it there instead. This
  store is for what only surfaces while doing the work: what broke, what the fix
  turned out to be, what the user wants done differently next time.
- For technical lessons, record repeated failed attempts followed by a verified
  solution, or a useful approach found only after substantial searching, time or
  token use. The entry must help avoid repeating that cost in a similar case.
- Preserve the failed routes worth avoiding, the successful method, its applicable
  conditions and evidence. Do not invent retry counts, token totals or timings;
  measured costs are not required to recognize an expensive investigation.
- Do not save routine successes, generic advice, work logs or speculative fixes.
  Explicit user preferences remain eligible under the same project-specific rules.
- Not task lists and not open bugs — those belong in the project's issue tracker
  or its `AGENTS.md`.

---

## When an old lesson fails

1. Read the existing entry and compare its assumptions with the current version,
   environment, inputs and usage. Investigate the failure with source evidence or
   a focused reproduction; one failure alone does not establish invalidity.
2. Distinguish a transient problem or use outside the entry's conditions from a
   method that no longer works under those conditions. If the cause is unresolved,
   report the uncertainty without rewriting the old lesson as disproven.
3. Once invalidity is confirmed, use `add` with the same key to replace the current
   lesson without asking for approval. Record the evidence, affected conditions
   and verified replacement. If no replacement is known, state that limit instead
   of continuing to recommend the failed method. Keep any conditions where the
   old method remains valid, and preserve applicable absorption relationships.
4. Read the entry back to verify the correction. Keep the append-only history;
   do not manually edit or delete store lines.

## How other skills and agents record learnings

For delegated work, the main agent supplies relevant stored lessons in each
worker's prompt. Workers return costly trial-and-error findings and evidence,
including suspected stale entries, to the main agent rather than writing the
store themselves. The main agent verifies, deduplicates and records qualifying
lessons or confirmed corrections without asking for approval.

One call, no format duplication:

```bash
python3 <project-memory>/scripts/memory.py add \
  --type pitfall --key '<key>' --insight '<concise reusable lesson>' \
  --confidence 8 --source '<skill-or-agent-name>' --files '<file>'
```

Same rules apply: confidence 7 or above, project-specific, actually encountered.

---

## Storage and export

The shared store is `~/.tstack/projects/<slug>/learnings.jsonl`. Every run of the
script first moves a store left in `~/.mystack` to the new location and reports
what it moved on stderr, so never copy or delete either folder by hand.
To locate it or understand its format, read
[Storage format and project identity](references/store-operations.md#where-it-lives).

When asked to export memory for a handover or project document, read
[Export](references/store-operations.md#export). Do not append it to project documents automatically.
