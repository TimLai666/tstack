# Store operations

Use the script path set in the main skill (`_MEM`) for these commands.

## Merging entries

Merge two entries when they turn out to have the same root cause, not when the
output feels long. The merged insight has to carry the specifics that made each
one worth keeping — the number, the file, the thing that actually broke.
Collapsing two concrete lessons into one general statement throws away the only
thing this store holds that `AGENTS.md` does not.

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
entry instead, so nothing drops out of the output and `search` still finds them
under their old keys. No line ever leaves the file. This is not a delete: re-add
an absorbed key with a fresh timestamp and it stands on its own again.

---

## Where it lives

`~/.tstack/projects/<slug>/learnings.jsonl`, one JSON object per line:

```json
{"ts":"2026-04-04T10:00:00Z","type":"pitfall","key":"n-plus-one-products","insight":"Product.includes(:variants) needed in catalog controller","confidence":9,"source":"user-stated","branch":"feat/catalog","files":["app/controllers/catalog_controller.rb"]}
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

The format is deliberately boring: append-only, one line per learning, no index
and no lock. Any agent, in any language, can read it.

---

## Export

Turn the memory into markdown for a `CLAUDE.md`, `AGENTS.md` or handover doc:

```bash
python3 "$_MEM" load --all
```

`--all` matters here: the default view collapses most entries to their key, which
is right for loading context and wrong for a handover document.

The output is already markdown. Copy it, or append it to the target file if the
user asks. Never append automatically — that file is version-controlled and
shared with other people.
