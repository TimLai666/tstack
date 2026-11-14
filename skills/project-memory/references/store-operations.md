# Store operations

Use the script path set in the main skill (`_MEM`) for these commands.

## Merging entries

Merge two entries when they turn out to have the same root cause, not when the
output feels long. The merged insight has to carry the specifics that made each
one worth keeping: the number, the file, the thing that actually broke.

A merge is an ordinary `add` that names what it now covers:

```bash
python3 "$_MEM" add \
  --type pitfall \
  --key skill-instructions-need-an-execution-point \
  --insight '<concise lesson, keeping the specifics from both>' \
  --confidence 8 \
  --absorbs 'skill-write-actions-need-a-moment,printed-suggestion-is-not-an-executed-step'
```

The absorbed keys stop taking a line of their own and print after the merged
entry instead, and `search` still finds them under their old keys. No line ever
leaves the file. To restore an absorbed key, re-add it with a fresh timestamp;
it stands on its own again.

---

## Where it lives

`~/.tstack/projects/<slug>/learnings.jsonl`, one JSON object per line:

```json
{"ts":"2026-04-04T10:00:00Z","type":"pitfall","key":"node-18-default-here","insight":"This machine defaults to node 18 and the build needs 20; nvm use 20 before building","confidence":9,"source":"user-stated","branch":"feat/catalog","files":["package.json"]}
```

`<slug>` comes from the git remote (`org-repo`), falling back to the directory
name when there is no remote. Run `python3 "$_MEM" path` to see it.

Earlier versions kept the store in `~/.mystack`. Every command checks for that
folder before doing anything else and moves its whole content to `~/.tstack`:

- `~/.tstack` absent: the folder is renamed, so every project and any other file in it comes along.
- Both present: files are moved one by one. When a project has `learnings.jsonl` on both sides, the old lines that the new file lacks are appended to it.
- Any other file that exists on both sides stays in `~/.mystack` and is listed on stderr for a manual merge.

An agent still running an older copy of this skill keeps writing to `~/.mystack`;
the next run of this version picks those lines up the same way.

The wider stores use the same format: global preferences in `~/.tstack/global/learnings.jsonl`, machine facts in `~/.tstack/machine/learnings.jsonl`, and facts about a remote host in `~/.tstack/hosts/<name>/learnings.jsonl`. All of them live on the machine the agent runs on and are not tied to a project. Their `branch` field is empty.

A line with a `promoted_to` field is the mark left by `promote`: a copy of the
entry naming the repository file it was written into. It is the newest line for
its key until the key is re-added.

The format is append-only, one line per learning, with no index and no lock.

---

## Export

Turn the memory into markdown for a handover doc:

```bash
python3 "$_MEM" load --all
```

Use `--all` for an export; the default view collapses most entries to their key.
Entries marked `(promoted to …)` are already in the repository; leave them out
of the export. `AGENTS.md` is not an export target: a lesson reaches it through
promotion, one rule line at a time.

The output is already markdown. Copy it, or append it to the target file if the
user asks. Never append automatically.
