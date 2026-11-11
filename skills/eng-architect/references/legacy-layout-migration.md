# Legacy layout migration

Engineering documents live under `engineering/`, as the core's [Engineering Documents](../../software-engineering-guidelines/SKILL.md#engineering-documents) sets. Projects set up earlier keep them elsewhere, and some of the older documents no longer exist as a kind:

| Older location | Now |
|---|---|
| `ENG.md` | `engineering/architecture.md` |
| `docs/tickets/`, `docs/dev/tickets/` | `engineering/tickets/`, filed into `doing/` and `done/` by each ticket's old status field |
| `docs/dev/specs/` | `engineering/specs/` |
| `delivery-plan.md`, `delivery-status.md` | No status file. Its decisions become decision records, its blockers go on their tickets |
| `DESIGN-REVIEW.md`, `docs/dev/ui-review.md` | No review record. Open items become fix tickets, component copy and states go into the feature's specification |
| `docs/security-scan/report.md`, `docs/dev/security-scan.md` | No kept report. Unfixed findings become fix tickets |
| `docs/software-engineering-guidelines/` | The notes of the ticket the work belongs to |

`delivery-plan.md` is the oldest name of the status record. It must not be mistaken for a feature plan by a `*-plan.md` search, and a feature plan with that name is not moved.

`PLAN.md`, `TODOS.md`, `docs/plans/` and `docs/plan-grilling/` were never written by this skill. Leave them where they are.

## When to run it

Run it when any older location above exists in the project, or when a ticket file still carries a status field, before creating or updating an engineering document.

## Decide once

Moving files changes the user's project, so the user decides.

1. Look up the decision in project memory through **project-memory**, under the preference key `engineering-layout-migration`. An older entry under `delivery-status-migration` counts for the status record only.
2. With no decision recorded, run the script without `--apply`, show the user what would move, and ask whether to migrate, keep the old layout, or defer.
3. Record the answer through **project-memory** with that key and source `eng-architect`, including any condition for asking again. Recording the decision is separate from carrying it out.

While the answer is pending, and when the user keeps or defers the old layout, keep using the existing files. Do not create `engineering/` beside them.

## Migrate

The script is `scripts/migrate_layout.py`; its `--help` lists the moves and its rules. It moves files, files tickets by their old status and removes that field. It does not rewrite content: the older documents that have no place in the new layout are parked under `engineering/reports/legacy-*`, and carrying their content over is done by hand in step 5.

1. Run it without `--apply` and read the report.
2. Resolve every blocked move first. A move is blocked when its destination exists or two older files share one destination: compare them, merge the current content into one file, and remove the other only after the user agrees.
3. Run it with `--apply`.
4. File by hand each ticket the report could not file, and fill in each `**Blocked:**` line it created.
5. Carry over what the report lists under "Carry over by hand":
   - **`engineering/architecture.md`**: bring it to the current form in Step 4 of the [Engineering workflow](engineering-workflow.md). Move the reasoning of each hard-to-reverse choice to a [decision record](decision-records.md) and the migration steps of one change to its ticket.
   - **`legacy-status.md`**: write each decision that still holds as a decision record. Check that every blocker it names is on its ticket and that every ticket it calls done is in `done/`.
   - **`legacy-ui-review.md`**: write each open item as a fix ticket, and each component's copy and states into the `Screens` section of that feature's specification.
   - **`legacy-security-scan.md`**: write each unfixed finding as a fix ticket. When the repository is public or its visibility is unknown, get the user's confirmation first.
   - **Other files under `engineering/reports/`**: move what is still needed into the notes of the ticket it belongs to.

   Show the user what was carried over from each parked file, and delete the file once they agree.
6. Update every reference the report lists, in `AGENTS.md` first, and replace its required-artifacts entries with the current set from Step 5b of the engineering workflow.
7. Write `engineering/README.md` as the core's Engineering Documents sets.
8. When tickets are mirrored to an issue tracker, regenerate each issue body so that it names the ticket file's new path, as [Ticket lifecycle](ticket-lifecycle.md) sets. Report the issues that could not be updated.
9. Run the script once more. It reports nothing to move, nothing to carry over and no remaining mention.
10. Commit the moves on their own, separate from the content carried over, and record in project memory that the migration is complete.
