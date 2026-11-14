---
name: project-memory
description: "Shared cross-agent memory in four stores: project lessons, the user's preferences for every project, facts about this machine, and facts about remote hosts. This skill MUST be invoked when starting work in a project whose memory is not already in context, and again as the work wraps up to record what was learned. It MUST also be invoked on the triggers below, and SHOULD be invoked whenever the user states something worth remembering. A cross-project preference MUST go in the global store, not in the user's instruction files; a machine fact MUST go in the machine or host store; a project lesson that holds on any machine MUST be promoted into the project's AGENTS.md or engineering documents instead of staying in the store. It MUST NOT be used for task lists or open bugs. Triggers on: 記一下, 之前踩過什麼雷, 有什麼教訓, remember this, 把這個記起來, 以後都這樣, 這台沒裝"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - AskUserQuestion
metadata:
  version: "1.18.0"
---

## Purpose and workflow

Keep project-specific solutions that took repeated failed attempts or substantial searching, time or tokens to find, so the next agent can avoid repeating that work.

1. **Starting work in a project** — read this project's memory before reading code or making changes, without waiting to be asked. When the session opened with the memory already in context (the tstack session-start hook provides it in Claude Code), use that and do not run `load` again. When it is absent, or only keys are listed, run `load`. Search related keys before working in that area.
2. **When something is learned or work wraps up** — check the recording criteria below and run `add` for qualifying lessons. Report saved entries; if nothing qualifies, no announcement is needed.

## The script

All reads and writes go through `scripts/memory.py` in this skill's own
directory. Do not hand-build JSON with `echo`.

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
| `promote --key K --to PATH` | Mark a project lesson as written into the repository file at PATH, so `load` stops showing it |
| `search QUERY` | Filter learnings by substring |
| `stats` | Counts by type and average confidence |
| `path` | Print the store path for this project |

Add `--global`, `--machine` or `--host NAME` to any of them to work on one of the wider stores instead; see [Global, machine and host stores](#global-machine-and-host-stores).

---

## Load

```bash
python3 "$_MEM" load
```

`pitfall`, `pattern` and `preference` entries print in full. `architecture` and
`tool` entries print as a bare key list:

```
## Only recorded here (pitfall, pattern, preference)
- **node-18-default-here** (9/10) — this machine defaults to node 18 and the build needs 20; run nvm use 20 first

## Index — 42 more, run `search <key>` for the full text
- **architecture**: no-orm-raw-sql, events-are-append-only
- **tool**: rg-over-grep
```

Every key is always listed, however large the store gets. When a key looks
related to what you are about to do, run `search <key>` before you touch that
area:

```bash
python3 "$_MEM" search node-18-default-here
```

Already deduplicated: same key, newest wins. `NO_LEARNINGS` means a fresh
project; carry on. Damaged lines are skipped and reported rather than aborting.

`--all` expands everything, for when you want to read the whole store, and adds
the entries already promoted into the repository, each with where it went.

`load` ends with a recording reminder; `--json` and `--all` omit it.

---

## Add

Draft the fields from what actually happened and write qualifying entries without
asking the user to supply or approve each field. Report what was saved.

1. **Type** — `pitfall` for something that actually went wrong, `pattern` for a
   way of working that turned out to hold, `preference` for how the user wants
   things done. Those three load in full. `architecture` and `tool` describe how
   the project is put together and load as keys only. Pick by which of those the
   entry is, not by how important it feels or by which one gets shown.
2. **Key** — kebab-case, and it must describe the lesson, for example
   `node-18-default-here`, not `lesson-001`. The script rejects generic and
   numbered keys.
3. **Insight** — a concise, reusable lesson: applicable conditions, failed approaches worth avoiding, the verified solution and its evidence or location. Include the root cause when confirmed; label anything still uncertain.
4. **Confidence** — 1-10

```bash
python3 "$_MEM" add \
  --type pitfall \
  --key node-18-default-here \
  --insight 'This machine defaults to node 18 and the build needs 20; nvm use 20 before building. Found after the build failed on an unknown syntax error' \
  --confidence 9 \
  --files 'package.json'
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
  What holds beyond this project goes in one of the [Global, machine and host stores](#global-machine-and-host-stores).
- A pitfall met for the second time in this project MUST be recorded, even when
  each occurrence was cheap. Say in the report that it is a second occurrence.
- A rule the user was promised will be remembered is written in that same turn.
  Report its key and a one-sentence summary of what was saved.
- A lesson that holds on any machine goes into the repository, not into this
  store; see [Promoting a lesson into the repository](#promoting-a-lesson-into-the-repository).
  This store keeps what depends on this machine as well as on the project.
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

## Promoting a lesson into the repository

This store lives in the user's home directory and does not travel with the
repository. A lesson that an agent on any other machine would need is written
into the repository instead.

**Machine-bound or portable.** A lesson is machine-bound when it depends on
something about this machine: a local path, what is or is not installed here,
where a credential is kept, this machine's operating system, shell or tool
version. It stays in this store (or, when it says nothing about the project,
goes in the machine store). Every other lesson is portable and is promoted.
Split a mixed lesson into its portable part and its machine-bound part. A lesson
that must not be in the repository (a confidential host name, where a credential
is kept, something about one user's own account) stays in this store whatever
machine it holds on.

**Where a portable lesson goes**, by type:

| Type | Home in the repository |
|---|---|
| `preference`, `pitfall`, `pattern` | The `AGENTS.md` of the directory the lesson is about, the root one when it concerns the whole project, as one line: the condition, then what to do |
| `architecture` | `engineering/architecture.md` when the project keeps one, otherwise `AGENTS.md` |
| `tool` | Almost always machine-bound; when it is not, `AGENTS.md` |

The line in `AGENTS.md` states the rule only, without the reason or the story,
following the core's [Agent Context Files](../software-engineering-guidelines/references/changing-code.md#agent-context-files).
The failed routes and the evidence go into the body of the commit that writes
the line, one paragraph per lesson, so that `git log -S` on the rule finds them.
Write the promotion as a commit of its own.

**When.**

1. At recording time: a portable lesson is written into the repository directly and does not enter this store.
2. When a stored lesson is applied a second time, that is, it decides what the agent does in this project: promote it then.
3. When the user asks to tidy the project's memory or documents.

When the repository cannot take the line now (it is not the user's to change,
the file has uncommitted changes of someone else, or the user does not want a
commit at this point), record the lesson in this store and promote it later.
A lesson is never dropped because it could not be promoted.

**How.** Write the line into the file, commit it with the story in the commit
body, then mark the entry here:

```bash
python3 "$_MEM" promote --key run-migrations-before-tests --to AGENTS.md
```

`load` stops showing a promoted entry and `load --all` lists it with where it
went; `search` still finds it. No line leaves the file. To bring an entry back,
re-add the same key. A promoted lesson that turns out wrong is corrected in the
file it went to, not by re-adding it here.

---

## Global, machine and host stores

| It is about | Record with | Stored on this machine at |
|---|---|---|
| How the user wants work done in every project: a standing preference, a way of working they corrected or confirmed | `add --global` | `~/.tstack/global/` |
| The machine the agent runs on | `add --machine` | `~/.tstack/machine/` |
| A machine reached from here, for example over SSH | `add --host NAME` | `~/.tstack/hosts/NAME/` |

- A machine fact holds in every project worked on there: a tool that is or is not installed and where, a path that cannot run programs, which package manager or shell works, where a credential is configured, how a local service is reached.
- A global preference is recorded here and nowhere else. Do not add it to the user's own instruction files such as `~/.claude/CLAUDE.md` or a home-level `AGENTS.md`; those are the user's to edit. A preference that applies to this project only is promoted into the project's `AGENTS.md`, or stays in the project store when it is machine-bound.
- `NAME` is the name used to reach the host, such as its SSH alias. Use the same name every time.
- Host facts are recorded from this machine and stay on it. Nothing is written on the remote host.
- Each entry in these stores is at most 300 characters: the condition, then what to do. Leave the story of how it was found out.
- `load` prints the global preferences and the machine facts in full, and the names of the hosts that have facts. Before working on a remote host, run `load --host NAME`. In Claude Code the tstack guard hook shows that host's facts on the first `ssh`, `mosh`, `sftp`, `scp` or `rsync` command that names it; run the load yourself when the host is reached another way, such as through a jump host or a name held in a variable.
- A fact that something is absent, not installed or impossible says how that was checked. Before relying on one whose recorded date is old, or after the environment changed, check again; when it no longer holds, re-add the same key with the current state.
- Record the location of a credential, never its value.
- The second-occurrence rule above applies here too.

```bash
python3 "$_MEM" add --machine --type tool --key temp-folder-blocks-exe \
  --insight 'Programs started from the temp folder are blocked; build and run from the user data folder' \
  --confidence 9
python3 "$_MEM" add --host devbox --type tool --key docker-needs-sudo \
  --insight 'docker on devbox needs sudo; the user is not in the docker group' --confidence 9
```

---

## When an old lesson fails

1. Read the existing entry and compare its assumptions with the current version,
   environment, inputs and usage. Investigate the failure with source evidence or
   a focused reproduction; one failure alone does not establish invalidity.
2. Distinguish a transient problem or use outside the entry's conditions from a
   method that no longer works under those conditions. If the cause is unresolved,
   report the uncertainty without rewriting the old lesson as disproven.
3. Once invalidity is confirmed, use `add` with the same key to replace the current
   lesson without asking for approval. A lesson already promoted into the
   repository is corrected in the file it went to instead; re-adding it here
   would bring it back into the store. Record the evidence, affected conditions
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

Record each lesson with one call:

```bash
python3 <project-memory>/scripts/memory.py add \
  --type pitfall --key '<key>' --insight '<concise reusable lesson>' \
  --confidence 8 --source '<skill-or-agent-name>' --files '<file>'
```

Same rules apply: confidence 7 or above, project-specific, actually encountered,
and a portable lesson is promoted into the repository rather than stored.

---

## Storage and export

The project store is `~/.tstack/projects/<slug>/learnings.jsonl`; the wider stores sit beside it under `~/.tstack/global/`, `~/.tstack/machine/` and `~/.tstack/hosts/<name>/`. Every run of the
script first moves a store left in `~/.mystack` to the new location and reports
what it moved on stderr, so never copy or delete either folder by hand.
To locate it or understand its format, read
[Storage format and project identity](references/store-operations.md#where-it-lives).

When asked to export memory for a handover or project document, read
[Export](references/store-operations.md#export). Do not append it to project documents automatically.
