# Ticket Breakdown Guidelines

Each ticket defines the next verifiable result. These rules apply whether the tickets land as OpenSpec changes or as plain markdown files.

## Three levels

| Level | What it is | Where it lives |
|---|---|---|
| Epic | A capability area of the product | A field on the ticket |
| User Story | One thing a person can do | A field on the ticket |
| Task | One implementable slice of a story | The ticket itself — one file, one change |

Only the Task level becomes a file. Epic and Story are labels on the ticket, used to group the tickets and to check coverage.

## The slicing axis

**Cut by what someone can do, not by which layer the code sits in.**

A ticket is one narrow path through every layer it needs (schema, logic, screen, tests), and it is demoable or verifiable on its own once done. Do not write a horizontal slice, such as a ticket that delivers "all the API endpoints" or "the whole data model".

Rules:

- Every ticket title reads as "<who> can <do what>". A title whose subject is a module, a layer or a technology gets rewritten.
- Test each ticket: once this is done, can anyone see or use the difference? If not, it is not a feature ticket; only the two exceptions below may be such tickets.
- Layers still decide the order **inside** one ticket: schema first, then logic, then screen. Never use layers to split the ticket set.

When the work has a specification, its scope items were already written this way and each one maps to a story. When it did not, do that rewrite here before slicing.

## Exception 1 — shared foundations

Collect project scaffolding, auth, the design system, and core tables that several stories sit on into one foundation ticket, instead of spreading them across whichever features touch them first, and give every ticket that needs them a blocking edge back to it.

One foundation ticket per shared base. Do not create one for an Epic whose stories share nothing.

## Exception 2 — wide refactors

A wide refactor is one mechanical change (rename a column, retype a shared symbol) whose blast radius fans across the codebase, so a single edit breaks call sites everywhere and no vertical slice can land green. Sequence it as expand–contract instead:

1. **Expand**: add the new form beside the old so nothing breaks.
2. **Migrate**: move call sites over in batches sized by blast radius (per package, per directory), one ticket per batch, each blocked by the expand.
3. **Contract**: delete the old form once no caller remains, blocked by every migrate batch.

When even the batches cannot stay green alone, keep the sequence but let them share an integration branch, and have all of them block one final integrate-and-verify ticket. Only that ticket is required to land green.

## Blocking edges

Every ticket declares the tickets that must finish before it can start. A ticket with no blockers can start immediately; the tickets whose blockers are all done are the frontier, and anything on the frontier is safe to pick up.

Draw an edge only where one ticket genuinely gates another: a shared table, an auth boundary, a contract the other side calls. A preferred order alone is not a blocking edge.

## Coverage check

After slicing, go back over the per-feature analysis (1b-1d) and assign every row to exactly one ticket:

- each row of the error/rescue map
- each shadow path
- each interaction edge case

A row no ticket owns is a missing ticket; add it now, not later. A row owned by two tickets means their boundary is unclear; redraw it. The same check applies upward: every story has at least one ticket, and the tickets under a story cover its whole acceptance criteria. Every scope item of the specification has at least one ticket, and the tickets that name it cover all of its `Done when` conditions. A ticket that names no scope item is one of the two exceptions below or is outside the specification.

## Where the tickets land

Use the project's established ticket system and prior user decisions. Ask only when the destination remains unresolved and affects the workflow. The formats below are defaults when no arrangement exists; preserve the existing system's format while retaining behavior-based slices, acceptance coverage, and real blockers.

### Plain markdown (default)

One file per ticket under `docs/dev/tickets/`, numbered from `01` in dependency order:

```md
# 07 — A customer can choose a service and a time slot

**Epic:** Booking flow
**User Story:** A customer can complete a booking
**Spec:** booking.md S3
**Blocked by:** 01 Project scaffold, 04 Services table
**Status:** ready

## What it delivers
[The end-to-end behaviour this makes work, from the user's side.]

## Acceptance criteria
- [ ] ...
- [ ] ...
```

Use this directory as the backlog location when handing off implementation.

### OpenSpec

When the project has an `openspec/` directory and the `openspec` CLI is available, one ticket is one change, never one task. The ticket's acceptance criteria become the change's requirements and scenarios, which are the specification as [Specification guidelines](spec-guidelines.md#openspec) sets out; the ordering inside one ticket belongs in its `tasks.md`.

OpenSpec has no dependency relationship *between* changes. Keep the blocking edges in `delivery-status.md`: map each change to one milestone id and let the milestone order carry the sequence. Do not invent a `blocked by` field inside the change.

OpenSpec does not stop anyone from starting a change whose foundation is unbuilt. Do not start such a change.

## Avoid

- One ticket for an entire phase, or one mixing unrelated capabilities.
- File paths and code snippets in the ticket body. The exception is a snippet that encodes a decision more precisely than prose can (a state machine, a schema, a type shape); trim it to the decision, not a working demo.
- A ticket that cannot be validated on its own.
- A plan that points at a vague bucket like `backend cleanup`.

## Quality checks

- The next agent can pick one ticket off the frontier and start without re-planning.
- Every ticket title survives the "can anyone see or use the difference" test, or is one of the two exceptions.
- Ticket size is small enough that done-or-not-done is not a judgement call.
- Every story has ticket coverage; every error path, shadow path and edge case has exactly one owner.
- Blocking edges reflect real gates, not preferred order.
