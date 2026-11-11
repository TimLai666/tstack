# Legacy layout migration

Engineering documents live under `engineering/`, as the core's [Engineering Documents](../../software-engineering-guidelines/SKILL.md#engineering-documents) sets. Projects set up earlier keep them elsewhere:

| Older location | Now |
|---|---|
| `delivery-plan.md`, `delivery-status.md` | `engineering/status.md` |
| `ENG.md` | `engineering/architecture.md` |
| `DESIGN-REVIEW.md`, `docs/dev/ui-review.md` | `engineering/reviews/ui.md` |
| `docs/security-scan/report.md`, `docs/dev/security-scan.md` | `engineering/reviews/security.md` |
| `docs/tickets/`, `docs/dev/tickets/` | `engineering/tickets/` |
| `docs/dev/specs/` | `engineering/specs/` |
| `docs/software-engineering-guidelines/` | `engineering/tasks/` |

`delivery-plan.md` is the oldest name of the status record. It must not be mistaken for a feature plan by a `*-plan.md` search, and a feature plan with that name is not moved.

`PLAN.md`, `TODOS.md`, `docs/plans/` and `docs/plan-grilling/` were never written by this skill. Leave them where they are.

## When to run it

Run it when any older location above exists in the project, before creating or updating an engineering document.

## Decide once

Moving files changes the user's project, so the user decides.

1. Look up the decision in project memory through **project-memory**, under the preference key `engineering-layout-migration`. An older entry under `delivery-status-migration` counts for the status record only.
2. With no decision recorded, run the script without `--apply`, show the user what would move, and ask whether to migrate, keep the old layout, or defer.
3. Record the answer through **project-memory** with that key and source `eng-architect`, including any condition for asking again. Recording the decision is separate from carrying it out.

While the answer is pending, and when the user keeps or defers the old layout, keep using the existing files. Do not create `engineering/` beside them.

## Migrate

The script is `scripts/migrate_layout.py`; its `--help` lists the moves and its rules.

1. Run it without `--apply` and read the report.
2. Resolve every blocked move first. A move is blocked when its destination exists or two older files share one destination: compare them, merge the current content into one file, and remove the other only after the user agrees.
3. Run it with `--apply`.
4. Update every reference the report lists, in `AGENTS.md` first. Add the specification and status entries `AGENTS.md` lacks.
5. Write `engineering/README.md` as the core's Engineering Documents sets.
6. Run the script once more. It reports nothing to move and no remaining mention.
7. Commit the moves on their own, separate from content changes, and record in project memory that the migration is complete.
