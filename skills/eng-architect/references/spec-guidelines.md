# Specification guidelines

The specification states what is to be built: who can do what, and how to tell that it is done. Tickets are cut from it, and it stays the reference the tickets and the finished work are checked against.

## When one is required

A specification exists and is confirmed before any ticket is written. Write or update one when work is about to be cut into tickets, or when a feature is too large for a single ticket.

A bug fix, a small change, and a bounded architecture question do not get a specification.

## Where it lives

| Project | Specification |
|---|---|
| Has its own location or format for specifications | That location and format. Fill what the sections below require and the project's format lacks |
| Uses OpenSpec | `openspec/specs/` is the specification. Follow [OpenSpec](#openspec) and write no separate file |
| Neither | `engineering/specs/<feature>.md`, one file per feature, placed as the core's [Engineering Documents](../../software-engineering-guidelines/SKILL.md#engineering-documents) sets |

A specification is a state file: one per feature, updated in place, with no date or branch in its name.

## What it contains

```md
# Spec: [feature]

## Goal and problem
[What is wrong or missing today, for whom, and what will be true when this is done.]

## Scope
### S1 — [who] can [do what]
- Done when: [a condition someone can check]
- Done when: ...

### S2 — ...

## Not doing
- [Excluded or deferred item] — [why, and when it would be reconsidered]

## Flows and exceptions
[The main flow of each scope item, and what happens in each exceptional case.]

## Screens
[For each screen or component: its states (default, loading, empty, error, disabled) and the exact copy of labels and messages.]

## Constraints
[Technical and environment limits, and the data and formats this touches.]

## Success measures
[How to tell, after delivery, that the goal was met.]

## Assumptions and risks
- [Assumption] — [what changes if it is wrong]

## Decisions
### [Topic]
- Chosen: [option and reason]
- Rejected: [option and reason]

## For the implementer
- May decide: [details left to the implementer]
- Must ask: [choices that go back to the user]
```

Rules for the content:

- Every scope item reads "<who> can <do what>", has an id that never changes once tickets refer to it, and carries at least one checkable condition. A module, a layer or a technology is not a scope item.
- The specification states the behavior the feature has now, and is updated in place when a later change alters it. Architecture and the order of implementation go in `engineering/architecture.md` and the tickets.
- `Decisions` holds the choices about this feature's behavior. A hard-to-reverse choice that reaches across features is a [decision record](decision-records.md).
- A reader with only this file can start work. Do not point at the conversation for a missing fact.
- Leave out a section that has nothing in it. `Scope` and `Not doing` are always present.

## Where the content comes from

Take it from the user's messages, the project's existing documents and prior decisions. Ask only for the choices that remain open and would change the scope.

A plan saved by the `plan-grilling` skill, by default under `docs/plan-grilling/`, is a source and not the specification. Carry it over:

| Plan section | Goes to |
|---|---|
| Goal and constraints | `Goal and problem`, `Constraints`, and the outline that `Scope` has to cover |
| How to evaluate it | The `Done when` conditions and `Success measures` |
| Decision record | `Decisions`, including the rejected options. Reuse them without asking again |
| Unresolved items | Settle the ones a scope item depends on before confirming; record the rest under `Assumptions and risks` |
| Next step | Not carried over. Ticket order decides it |

## Confirmation

Present the scope items, the `Not doing` list and the decisions made on the user's behalf, and get the user's confirmation before cutting tickets. A specification that only restates what the user already confirmed item by item needs no second round.

## Keeping it in sync

When the requirement changes after the specification is confirmed, whether the user changes it or the work shows it cannot hold:

1. Update the specification first, in place. Add, change or remove the scope items and their conditions, move what is dropped to `Not doing`, and record the reason under `Decisions`.
2. Update every ticket that refers to a changed scope item: its acceptance criteria, its blockers, and its status when finished work no longer matches. Add tickets for new scope items and close the tickets of removed ones.
3. Rerun the coverage check in [Ticket breakdown guidelines](ticket-breakdown-guidelines.md#coverage-check).
4. Move a ticket out of `done/` when its finished work no longer matches the specification.

Code does not change ahead of the specification. A change the user has not agreed to is asked about before step 1.

## OpenSpec

In an OpenSpec project the requirements and scenarios under `openspec/specs/` are the specification, and each change carries the delta it makes to them.

- A scope item is a requirement; its `Done when` conditions are that requirement's scenarios.
- New or changed scope goes into the delta specs of the change that delivers it. Do not edit `openspec/specs/` by hand; archiving the change updates it.
- What OpenSpec has no place for, such as `Not doing`, `Success measures` and `Assumptions and risks`, goes in the change's `proposal.md`.
- [Keeping it in sync](#keeping-it-in-sync) applies with the change as both the specification update and the ticket: revise the delta specs and `tasks.md` of the open change, or open a new change when the affected requirement is already archived.
