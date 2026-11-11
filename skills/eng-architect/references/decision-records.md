# Decision records

A decision record keeps why a choice was made, so that it is not argued again or undone by someone who does not know it was made.

## When to write one

Write one at the moment of the decision, when the choice is hard to reverse and reaches across features: a storage engine, an authentication method, a module boundary, a third-party service, a data format that others depend on.

Do not write one for a choice that follows from an existing record, for a detail one ticket can change freely, or for a decision about one feature's behavior. The last kind goes under `Decisions` in that feature's specification.

## Where and how

One file per decision under `engineering/decisions/`, placed as the core's [Engineering Documents](../../software-engineering-guidelines/SKILL.md#engineering-documents) sets, numbered from `0001` in the order written.

```md
# 0007 — Store uploads in object storage

**Status:** accepted
**Date:** 2026-03-14

## Context
[The situation and the forces that made a decision necessary.]

## Decision
[What was chosen, stated as what the project now does.]

## Options rejected
- [Option] — [why it lost]

## Consequences
[What becomes easier, what becomes harder, and what has to be true for this to keep holding.]
```

- A record is not rewritten after it is accepted. When a later decision replaces it, write the new record, and change only the old one's status line to `superseded by NNNN`.
- `engineering/architecture.md` describes the system as it is and links to the records that explain it. It does not repeat their reasoning.
- Before proposing a change that goes against a record, read it, and say in the proposal which condition of the record no longer holds.

A project that already keeps decision records elsewhere, for example under `docs/adr/`, keeps using that location and format.
