# Changing code and project files

The short form of these rules is in [SKILL.md](../SKILL.md). Read the part that matches what you are about to do.

## Complete, surgical changes

**Touch everything the task needs and nothing else. Clean up only your own mess.**

Plan each turn to finish the full authorized outcome, including implementation, integration, verification, and necessary repairs. Do not reserve required work for a later turn or wait for another prompt to finish it. Intermediate milestones organize the work within the turn; they are not delivery boundaries unless the user explicitly requested staged delivery. If a real blocker prevents completion, finish independent work and report the exact remaining gap and what is needed to resolve it.

Judge completion over the whole agreed feature or problem. Order intermediate work by the [whole-goal priorities](design.md#whole-goal-priority):

- A feature covers every layer, entry point, and edge case it needs.
- A fix covers the root cause, every occurrence of the same pattern, and the related edge cases. Do not stop at the reported spot.

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting; don't refactor things that aren't broken; don't delete pre-existing dead code. Mention what you spot and suggest how to handle it, under the recording rule below.
- Match existing style, even if you'd do it differently.
- Remove imports/variables/functions that YOUR changes made unused.
- Write and change files with the editing tools. Content that spans lines or contains non-ASCII characters, quotes or backslashes does not go through shell quoting or a heredoc.
- When a change has to be scripted, read the target first, confirm the number of matches the script will replace, write the result to a temporary file, and swap it in only after checking it. Before overwriting, restoring or discarding a file, read its full diff, including uncommitted work that is not yours.

Every changed line traces directly to the user's request.

**Recording rule:** Mention discovered out-of-scope issues to the user and record them using the project's existing follow-up location and conventions. In a project that keeps tickets, an issue that needs work becomes a ticket through **eng-architect**. If no location is established, use `## Follow-ups` in the project's `AGENTS.md`, creating the section or file if needed. Preserve existing content and avoid duplicate records. When an issue is resolved, follow the project's completion convention; under the default `Follow-ups` arrangement, remove the resolved entry. See [references/follow-ups-example.md](follow-ups-example.md) for the default format and examples.

**Git attributes:** Every Git repository has a root `.gitattributes`. When it is missing, create it while initializing the project or before the first commit of the current work. Start with `* text=auto eol=lf`, then add the entries the project's files need, such as `binary` for binary formats and `eol=crlf` for Windows scripts (`*.bat`, `*.cmd`). In a repository that already has commits, run `git add --renormalize .` after adding the file and commit the file with the resulting normalization as a separate commit. Preserve existing entries.

**Writing documents, rules, prompts, and skills:** Before editing existing content, load `human-writing` and apply [principle 8A](https://github.com/TimLai666/skills/blob/main/plugins/writing-and-design/skills/human-writing/references/human-writing-principles.md#8a-write-the-current-document-for-its-current-reader) for placement, consolidation, and consistency checks. If that skill is unavailable, read the linked rule before editing. When writing rules, prompts, or skills, state the rule itself. Do not explain the reason behind it, and do not write it as a change record (for example, a date and what it was changed from). Update the rule text in place.

## Agent Context Files

At every directory level of a project, `AGENTS.md` is the single home for agent instructions, and a `CLAUDE.md` in the same directory contains exactly this one line and nothing else:

```md
@AGENTS.md
```

Write the line verbatim, with no heading, explanation or other wording. Any other content, including a differently worded pointer, is replaced with it. Create missing files as needed.

This covers every `CLAUDE.md` in the project, not only the one at the root. The line in a nested `CLAUDE.md` refers to the `AGENTS.md` in that same directory; when that directory has none, create it there and move the content into it, rather than into the root file. Dependency and vendored directories are left alone.

- An instruction to add or change content in `CLAUDE.md` is applied to `AGENTS.md`.
- When `CLAUDE.md` holds instructions of its own, move them into `AGENTS.md`. Read both files in full, carry every rule over without dropping or rewording it, and place each one where it belongs in `AGENTS.md`. Where the two files contradict each other, ask the user which rule stands. Replace the content of `CLAUDE.md` with that line only after confirming every instruction is present in `AGENTS.md`.
- Do this when initializing project docs (e.g. `/init`) and before adding to either file. List every `CLAUDE.md` in the project first and handle all of them, each against the `AGENTS.md` beside it. When it is noticed during unrelated work, do it as a change of its own, in a separate commit.

An `AGENTS.md` at any directory level contains only what an agent must follow or check on every turn of work in that scope: operating rules and agent-facing reminders such as `## Follow-ups`. Project or module introductions, background, structure overviews, and usage notes go in the `README.md` at the same level. Move misplaced content to the correct file when editing either one.
