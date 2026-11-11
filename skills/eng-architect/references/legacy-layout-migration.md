# Legacy layout migration

Engineering documents live under `engineering/`, as the core's [Engineering Documents](../../software-engineering-guidelines/SKILL.md#engineering-documents) sets. Projects set up earlier keep them elsewhere, and some of the older documents no longer exist as a kind:

| Older location | Now |
|---|---|
| `ENG.md` | `engineering/architecture.md` |
| `docs/tickets/`, `docs/dev/tickets/` | `engineering/tickets/`, filed into `doing/` and `done/` by each ticket's old status field |
| `docs/dev/specs/` | `engineering/specs/` |
| `delivery-plan.md`, `delivery-status.md` | No status file. Its decisions become decision records, its blockers and handoff notes go on their tickets |
| `HANDOFF.md` at the root | `engineering/handoff.md`, keeping only unfinished work that has no ticket |
| `DESIGN-REVIEW.md`, `docs/dev/ui-review.md` | No review record. Open items become fix tickets, component copy and states go into the feature's specification |
| `docs/security-scan/report.md`, `docs/dev/security-scan.md` | No kept report. Unfixed findings become fix tickets |
| `docs/software-engineering-guidelines/` | The notes of the ticket the work belongs to |

`delivery-plan.md` is the oldest name of the status record. It must not be mistaken for a feature plan by a `*-plan.md` search, and a feature plan with that name is not moved.

The oldest versions of this workflow also left these, which the script reports and does not move, because people write files with the same names:

| File | When an earlier version of this workflow wrote it |
|---|---|
| `PLAN.md` at the root | Carry the scope it still describes into a specification |
| `TODOS.md` at the root | Turn each open item into a ticket, or into a `Follow-ups` entry in a project without tickets |
| `~/.mystack/projects/<project>/` in the user's home directory | Plans, design notes and checkpoints kept outside the repository. Carry over what the open work still needs |

Ask the user whether each of these came from this workflow, and delete it only after they agree.

In a project whose tickets are OpenSpec changes, the tickets stay under `openspec/`. Only the status record moves, and the order it set between changes is written into each change's `proposal.md`.

`docs/plans/` and `docs/plan-grilling/` belong to another skill. Leave them where they are.

## Other engineering documents under `docs/`

A project may keep further engineering documents under `docs/` in folders of its own, such as specifications, research notes or interface contracts. The script does not know which folders these are, so the user chooses:

1. The report of a run without `--apply` lists every directory under `docs/` that no move covers.
2. Ask the user which of them hold engineering documents and where each goes under `engineering/`. Recommend `engineering/specs` for specifications and `engineering/tickets` for tickets, and a folder of the same name for anything else. Documentation written for the project's users stays in `docs/`, and so does a folder another skill owns, such as `docs/design/`.
3. Pass each choice to the script as `--move SOURCE=DESTINATION`, in the dry run and in the applied run alike.

A project that keeps its specifications in a format of its own keeps that format after the move.

## When to run it

Run it when any older location above exists in the project, or when a ticket file still carries a status field, before creating or updating an engineering document.

## Decide once

Moving files changes the user's project, so the user decides.

1. Look up the decision in project memory through **project-memory**, under the preference key `engineering-layout-migration`. An older entry under `delivery-status-migration` counts for the status record only.
2. With no decision recorded, run the script without `--apply`, show the user what would move and which other directories under `docs/` it found, and ask whether to migrate, keep the old layout, or defer.
3. Record the answer through **project-memory** with that key and source `eng-architect`, including the directories the user chose to move or to leave, and any condition for asking again. Recording the decision is separate from carrying it out.

While the answer is pending, and when the user keeps or defers the old layout, keep using the existing files. Do not create `engineering/` beside them.

## Migrate

The script is `scripts/migrate_layout.py`; its `--help` lists the moves and its rules. It moves files, files tickets by their old status and removes that field, and rewrites links so that they keep resolving, both inside the files it moves and in other files that pointed at them. It does not rewrite content: the older documents that have no place in the new layout are parked under `engineering/reports/legacy-*`, and carrying their content over is done by hand in step 5.

1. Run it without `--apply` and read the report.
2. Resolve every blocked move first. A move is blocked when its destination exists or two older files share one destination: compare them, merge the current content into one file, and remove the other only after the user agrees.
3. Run it with `--apply`.
4. File by hand each ticket the report could not file, and fill in each `**Blocked:**` line it created.
5. Carry over what the report lists under "Carry over by hand":
   - **`engineering/architecture.md`**: bring it to the current form in Step 4 of the [Engineering workflow](engineering-workflow.md). Move the reasoning of each hard-to-reverse choice to a [decision record](decision-records.md) and the migration steps of one change to its ticket.
   - **`legacy-status.md`** and **`engineering/handoff.md`** moved from the root: write each decision that still holds as a decision record. Move each handoff note to the `## Notes` of the ticket it concerns, each working rule to `AGENTS.md`, and each fact about a machine to project memory through **project-memory**. A note about unfinished work that no ticket covers stays in, or goes to, `engineering/handoff.md`. Check that every blocker named is on its ticket and that every ticket called done is in `done/`. For OpenSpec changes, write what each change waits for into its `proposal.md`.
   - **`legacy-ui-review.md`**: write each open item as a fix ticket, and each component's copy and states into the `Screens` section of that feature's specification.
   - **`legacy-security-scan.md`**: write each unfixed finding as a fix ticket. When the repository is public or its visibility is unknown, get the user's confirmation first.
   - **Other files under `engineering/reports/`**: move what is still needed into the notes of the ticket it belongs to.
   - **Index files moved with the tickets**, such as a table of tickets or a generated list: remove every column or field that repeats a ticket's state, or regenerate the file from the directories.

   Show the user what was carried over from each parked file, and delete the file once they agree.
6. Update every reference the report lists, in `AGENTS.md` first, and replace its required-artifacts entries with the current set from Step 5b of the engineering workflow.
7. Write `engineering/README.md` as the core's Engineering Documents sets.
8. When tickets are mirrored to an issue tracker, regenerate each issue body so that it names the ticket file's new path, as [Ticket lifecycle](ticket-lifecycle.md) sets. Report the issues that could not be updated.
9. Run the script once more. It reports nothing to move, nothing to carry over and no remaining mention.
10. Commit the moves on their own, separate from the content carried over, and record in project memory that the migration is complete.
