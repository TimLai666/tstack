---
name: migrate-engineering-docs
description: "Move a project's engineering documents from older layouts into engineering/ (specifications, architecture, decision records, tickets filed by state, the handoff file), and bring AGENTS.md, CLAUDE.md and the project memory to the current rules. This skill MUST be used when the user asks to migrate, tidy or convert old engineering documents, before an engineering document is created or updated in a project that still has delivery-plan.md, delivery-status.md, ENG.md, DESIGN-REVIEW.md, docs/tickets/ or tickets with a status field, and when CLAUDE.md holds more than its pointer, AGENTS.md holds introductions, or the memory holds lessons that hold on any machine. It MUST show what would change and get the user's decision first, and MUST NOT delete a document before its content is carried over and the user agrees. It MUST NOT move documentation written for the project's users. Triggers on: 遷移工程文件、整理舊文件、搬舊文件、整理 AGENTS.md、精簡 AGENTS.md、記憶升級、migrate docs、migrate engineering docs"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
metadata:
  version: "1.3.0"
---

## Overview

Engineering documents live under `engineering/`, as the core's [Engineering Documents](../software-engineering-guidelines/SKILL.md#engineering-documents) sets. This skill brings a project that was set up earlier to that layout. The script moves files; this skill carries over the content that no longer has a document of its own, with the user's agreement at each point where something would be lost. It also brings the project's `AGENTS.md`, `CLAUDE.md` and memory to the rules that now govern them.

Run it on request, and when another skill finds an older layout before writing an engineering document.

## What older projects hold

| Older location | Now |
|---|---|
| `ENG.md` | `engineering/architecture.md` |
| `docs/tickets/`, `docs/dev/tickets/` | `engineering/tickets/`, filed into `doing/` and `done/` by each ticket's old status field |
| `docs/dev/specs/` | `engineering/specs/` |
| `HANDOFF.md` at the root | `engineering/handoff.md`, keeping only unfinished work that has no ticket |
| `delivery-plan.md`, `delivery-status.md` | No status file. Its decisions become decision records, its blockers and handoff notes go on their tickets |
| `DESIGN-REVIEW.md`, `docs/dev/ui-review.md` | No review record. Open items become fix tickets, component copy and states go into the feature's specification |
| `docs/security-scan/report.md`, `docs/dev/security-scan.md` | No kept report. Unfixed findings become fix tickets |
| `docs/software-engineering-guidelines/` | The notes of the ticket the work belongs to |
| `docs/plan-grilling/`, `docs/plans/` | `plans/` at the project root, where the `plan-grilling` skill saves plans |
| `docs/design/` | `design/` at the project root, where the `design-studio` skill keeps its working files |
| A `CLAUDE.md` with instructions of its own | The `AGENTS.md` beside it; `CLAUDE.md` keeps the single line the core's [Agent Context Files](../software-engineering-guidelines/references/changing-code.md#agent-context-files) sets |
| Introductions, structure overviews, installation and usage notes in an `AGENTS.md` | The `README.md` beside it |
| A project memory entry that holds on any machine | `AGENTS.md` or `engineering/architecture.md`, through **project-memory**'s [promotion rule](../project-memory/SKILL.md#promoting-a-lesson-into-the-repository); the entry is then marked promoted |

`delivery-plan.md` is the oldest name of the status record. A feature plan with that name is not moved.

The oldest versions of this workflow also left these, which the script reports and does not move, because people write files with the same names:

| File | When an earlier version of this workflow wrote it |
|---|---|
| `PLAN.md` at the root | Carry the scope it still describes into a specification |
| `TODOS.md` at the root | Turn each open item into a ticket, or into a `Follow-ups` entry in a project without tickets |
| `~/.mystack/projects/<project>/` in the user's home directory | Plans, design notes and checkpoints kept outside the repository. Carry over what the open work still needs |

In a project whose tickets are OpenSpec changes, the tickets stay under `openspec/`. Only the status record moves, and the order it set between changes is written into each change's `proposal.md`.

## Step 1 — Look, change nothing

The script is [scripts/migrate_layout.py](scripts/migrate_layout.py); its `--help` lists every move and rule. Run it from the project root without `--apply` and read the whole report: what would move, what is blocked, which tickets it cannot file, which files it found and will not move, which directories under `docs/` no move covers, and which `CLAUDE.md` and `AGENTS.md` files are not yet as the core sets. The sections it lists in `AGENTS.md` are candidates; read each one and decide whether it is a rule or an introduction.

Then read the project's memory through **project-memory** (`load --json` gives every entry that is not yet promoted) and sort each entry by its [promotion rule](../project-memory/SKILL.md#promoting-a-lesson-into-the-repository): staying in the store, or going to a named file. Make the table of what goes where part of the report.

Work on a clean working tree, on a branch of its own. When the tree has uncommitted changes, ask the user how to proceed before going on.

## Step 2 — Get the user's decision

Moving files changes the user's project, so the user decides. Look up an earlier decision first: a line in `AGENTS.md` that keeps or defers the old layout, or an older entry in project memory through **project-memory** under the preference key `engineering-layout-migration` (`delivery-status-migration` counts for the status record only), which counts and is promoted into that `AGENTS.md` line. When the user started this skill themselves, that is the decision to migrate, and only the choices below remain. A decision to keep or defer the layout concerns the engineering documents only; the questions about `AGENTS.md` sections and memory entries are still asked, and Step 5 still runs for what the user agrees to.

Show the report in the user's language, then ask together:

- **Whether to migrate now, keep the old layout, or defer.** Skip this when the user asked for the migration.
- **Which other directories under `docs/` hold engineering documents**, and where each goes under `engineering/`. Recommend `engineering/specs` for specifications, `engineering/tickets` for tickets, and a folder of the same name for anything else. Documentation written for the project's users stays in `docs/`.
- **Whether `PLAN.md`, `TODOS.md` and files in the home directory came from this workflow**, when the report names them.
- **Which of the listed `AGENTS.md` sections are introductions** and go to `README.md`.
- **Which memory entries are promoted, and into which file.** Show the sorted table; the user may keep an entry in the store or change its destination.

When the user keeps or defers the old layout, write that as one line in `AGENTS.md`, with the condition for asking again, so that no agent on any machine starts the migration; the line is removed when the migration is done. While an answer is pending, and when the user keeps or defers the old layout, keep using the existing files and do not create `engineering/` beside them.

## Step 3 — Move

1. Resolve every blocked move first. A move is blocked when its destination exists or two older files share one destination: compare them, merge the current content into one file, and remove the other only after the user agrees.
2. Run the script with `--apply`, passing each chosen directory as `--move SOURCE=DESTINATION`.
3. File by hand each ticket the report could not file, and fill in each `**Blocked:**` line it created.
4. Commit the moves on their own, before carrying any content over.

A project that keeps its specifications in a format of its own keeps that format after the move.

## Step 4 — Carry over the content

The script parks the documents that no longer exist as a kind under `engineering/reports/legacy-*` and lists them under "Carry over by hand". For each one, write its content where it now belongs, show the user what went where, and delete the parked file once they agree.

| File | Carry over |
|---|---|
| `engineering/architecture.md` | Bring it to the form in Step 4 of **eng-architect**'s [Engineering workflow](../eng-architect/references/engineering-workflow.md). Move the reasoning of each hard-to-reverse choice to a [decision record](../eng-architect/references/decision-records.md), and the migration steps of one change to its ticket |
| `legacy-status.md`, and `engineering/handoff.md` moved from the root | Write each decision that still holds as a decision record. Move each handoff note to the `## Notes` of the ticket it concerns, each working rule to `AGENTS.md`, and each fact about a machine to project memory through **project-memory**. A note about unfinished work that no ticket covers stays in, or goes to, `engineering/handoff.md`. Check that every blocker named is on its ticket and that every ticket called done is in `done/`. For OpenSpec changes, write what each change waits for into its `proposal.md` |
| `legacy-ui-review.md` | Write each open item as a fix ticket, and each component's copy and states into the `Screens` section of that feature's specification |
| `legacy-security-scan.md` | Write each unfixed finding as a fix ticket. When the repository is public or its visibility is unknown, get the user's confirmation first |
| Other files under `engineering/reports/` | Move what is still needed into the notes of the ticket it belongs to |
| Index files moved with the tickets, such as a table of tickets or a generated list | Remove every column or field that repeats a ticket's state, or regenerate the file from the directories |
| `PLAN.md`, `TODOS.md`, files in the home directory | Only when the user said they came from this workflow: carry over as the table in [What older projects hold](#what-older-projects-hold) sets |

Ticket formats, the notes section and fix tickets are set out in **eng-architect**'s [Ticket breakdown guidelines](../eng-architect/references/ticket-breakdown-guidelines.md) and [Ticket lifecycle](../eng-architect/references/ticket-lifecycle.md).

## Step 5 — Bring `AGENTS.md`, `CLAUDE.md` and the memory to the current rules

The user decided these moves in Step 2.

1. For every `CLAUDE.md` the report lists, apply the core's [Agent Context Files](../software-engineering-guidelines/references/changing-code.md#agent-context-files): move its instructions into the `AGENTS.md` beside it, then leave the single line.
2. Move each section the user called an introduction into the `README.md` beside that `AGENTS.md`, under a heading that fits the README. Rules stay; a section that mixes both is split.
3. For each memory entry the user agreed to promote: write the rule line into the file it goes to, as **project-memory**'s promotion rule sets. Commit all the lines of one run together, one paragraph per lesson in the commit body carrying its failed routes and evidence. Then mark each entry with `promote`.
4. Commit steps 1 and 2 as a change of their own, apart from the moves and the carried-over content.

## Step 6 — Finish

1. Update every reference the report lists, in `AGENTS.md` first, and replace its required-artifacts entries with the current set from Step 5b of the engineering workflow.
2. Write `engineering/README.md` as the core's Engineering Documents sets.
3. When tickets are mirrored to an issue tracker, regenerate each issue body so that it names the ticket file's new path, as the ticket lifecycle sets. Report the issues that could not be updated.
4. Run the script once more. It reports nothing to move, nothing to carry over, no remaining mention and no `CLAUDE.md` to bring over; every `AGENTS.md` section it still lists is one the user kept as a rule.
5. Commit the carried-over content separately from the moves. Remove the `AGENTS.md` line that kept or deferred the old layout, when there was one.

## Report

Tell the user, in this order:

- what moved, with the counts of tickets filed as open, in progress and done
- what was carried over from each parked document, and which parked files were deleted
- what moved between `CLAUDE.md`, `AGENTS.md` and `README.md`, and which memory entries were promoted into which file
- what is left for them: files not moved and why, issues not updated, references not changed, memory entries kept in the store and why
- what was not checked

## Completion check

- [ ] Nothing was overwritten, and nothing was deleted before its content was carried over and the user agreed.
- [ ] No ticket carries a status field, and each ticket is in the directory that matches its real state.
- [ ] No status file, review record or parked `legacy-*` file remains, or each one that remains is named in the report with the reason.
- [ ] `AGENTS.md` and `engineering/README.md` describe the layout the project now has.
- [ ] Every `CLAUDE.md` is the single pointer line, and `AGENTS.md` holds only what the core's [Agent Context Files](../software-engineering-guidelines/references/changing-code.md#agent-context-files) allows.
- [ ] Every memory entry the user agreed to promote is in its file, with its story in the commit body, and is marked promoted.
- [ ] A second run of the script reports nothing to move and no `CLAUDE.md` to bring over, and every `AGENTS.md` section it lists was decided by the user.
