---
name: eng-architect
description: "This skill MUST be used for architecture decisions, module boundaries, writing or updating the specification of a feature, or turning plans or specs into tickets. A requirement change in work that has a specification MUST update the specification and its tickets before the code. SHOULD be used when implementation requires unresolved architectural choices, the user is unsure how to divide the work, work on a ticket starts or finishes, or a ticket is too large and has to be split. MUST NOT expand an already specified implementation into a new planning exercise. MUST NOT be used to review built screens, which belongs to ui-review. Triggers on: 拆票, 寫規格, 規格書, 技術方案, 架構設計, 怎麼切模組, 拆任務, 切票, 排開發順序, 技術規劃."
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
  - AskUserQuestion
  - WebSearch
metadata:
  version: "4.3.0"
---

## Overview

Write the specification, design the architecture, and cut verifiable tickets from them. Preserve the requested scope and existing project decisions. Reviewing built screens belongs to **ui-review**.

## Workflow

Read [Engineering workflow](references/engineering-workflow.md) in full before the per-feature analysis, including its examples. Read the other references at the workflow step that needs them. Before cutting tickets, and whenever a requirement changes in work that has a specification, read [Specification guidelines](references/spec-guidelines.md).

## Working a ticket

In a project that keeps tickets, whoever implements one reads [Ticket lifecycle](references/ticket-lifecycle.md) at these points and follows it:

| Point | What it sets |
|---|---|
| Starting work | Which ticket can start, what to read, and whether the ticket has to be split first |
| A requirement changes, a finding is left for later, or the work spans sessions | Where each of these is written |
| The work is merged or handed back | Moving the ticket to `done/` in the same change |
| Tickets are mirrored to an issue tracker | Which side is the source and how the two stay in step |

A ticket's state is the directory it is in. Do not keep a status file.

## Shared decision rules

Use evidence from the project and prior user decisions. Analyze each feature's flow, failure paths, boundaries, and testing approach before consolidating the architecture.

Apply these checks before proposing an approach or writing tickets:

- **Constraints first.** Read the technical constraints in the project and user-level rules, such as allowed languages, runtimes, licenses and hosting. Drop every option that breaks one before comparing the rest. When recommending a tool or integration, check for an official or first-party one before a community one.
- **Define the terms that decide behavior.** When a requirement rests on a term with more than one reasonable reading, such as a time window, a total or a status, write a one-sentence definition with a worked example and confirm it before building on it.
- **List the counterpart operations.** Go through the core's [Counterpart Operations](../software-engineering-guidelines/SKILL.md#counterpart-operations) for each feature and put each one in scope or name it as out of scope.
- **Do not pick one reading of divergent behavior.** When the request allows materially different behaviors, such as rejecting versus queueing, present them with a recommendation and get the choice before designing around one.

Collect unresolved decisions that require user tradeoffs and present related choices together with a recommendation and consequences. Ask before changing agreed scope, architecture, workflows, or other consequential choices that are not authorized. Continue independent analysis while awaiting answers. Reuse settled decisions without asking again.

A request for discussion produces the corresponding analysis. An authorized implementation or ticket-writing request permits routine work within its agreed boundaries.

## Project records

A project that keeps these records in an older layout or whose tickets still carry a status field, is migrated first through **migrate-engineering-docs**.

Use existing documents and task systems that serve the purposes below. When no arrangement exists and full development handoff is needed, create the specification, `engineering/architecture.md`, ticket files, `engineering/README.md`, `AGENTS.md`, and the `CLAUDE.md` pointer. These locations follow the core's [Engineering Documents](../software-engineering-guidelines/SKILL.md#engineering-documents). For a bounded architecture decision, select the records needed for the requested outcome.

| File or location | Purpose | When to create or update | When to read |
|---|---|---|---|
| The existing specification, `openspec/specs/`, or `engineering/specs/<feature>.md` | What the feature does: scope items, exclusions, flows, constraints and decisions | Before cutting tickets; first of all when a requirement changes | Before working on a ticket of that feature, and when checking the result against the request |
| `engineering/architecture.md` | How the system is built: components, flows, test seams, standing assumptions | When the structure changes | Before changing the architecture, the testing strategy or a migration |
| `engineering/decisions/` | Why each hard-to-reverse choice was made, as [Decision records](references/decision-records.md) sets | At the moment of the decision | Before proposing to change such a choice |
| The existing ticket system, or `engineering/tickets/` | Each ticket's deliverable, acceptance criteria and blockers; its directory is its state | When asked to break down work or prepare development handoff | When picking up work |
| `engineering/README.md` | Index of the engineering documents for readers who do not use this stack | When `engineering/` is created or a kind of document is added or removed | On arrival |
| `AGENTS.md` | Project working rules and the locations and reading triggers of supporting records | When establishing coordination or changing working rules | Before starting project work |
| `CLAUDE.md` | Entry point directing agents to `AGENTS.md` | When establishing the default coordination setup; keep actual rules in `AGENTS.md` | As an entry point to the project rules |


Read existing content before updating it, preserve unrelated sections, and register actual artifact paths with when they must be read. Keep shared technical decisions in the architecture record and per-ticket acceptance criteria on the owning ticket.

## Completion check

- The result answers the requested architecture or ticketing need.
- Engineering analysis covers feature flows, failures, interaction boundaries, testing, and applicable migration risks; ticketing work assigns every analyzed acceptance item an owner and records real blockers.
- Unresolved assumptions and decisions are explicit. Project-required validation and delivery rules are followed.
- Updated records retain unrelated content, link to the actual sources, and identify the next verifiable action when handing off.
