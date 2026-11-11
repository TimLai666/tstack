---
name: eng-architect
description: "This skill MUST be used for architecture decisions, module boundaries, writing or updating the specification of a feature, or turning plans or specs into tickets. A requirement change in work that has a specification MUST update the specification and its tickets before the code. SHOULD be used when implementation requires unresolved architectural choices, the user is unsure how to divide the work, or work on a ticket starts or finishes. MUST NOT expand an already specified implementation into a new planning exercise. MUST NOT be used to review built screens, which belongs to ui-review. Triggers on: 寫規格, 規格書, 技術方案, 架構設計, 怎麼切模組, 拆任務, 切票, 排開發順序, 技術規劃."
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
  version: "4.0.0"
---

## Overview

Write the specification, design the architecture, and cut verifiable tickets from them. Preserve the requested scope and existing project decisions. Reviewing built screens belongs to **ui-review**.

## Workflow

Read [Engineering workflow](references/engineering-workflow.md) in full before the per-feature analysis, including its examples. Read the other references at the workflow step that needs them. Before cutting tickets, and whenever a requirement changes in work that has a specification, read [Specification guidelines](references/spec-guidelines.md).

## Working a ticket

In a project that keeps tickets, these apply to whoever implements one. Status sections and their update rules are in [Delivery status guidelines](references/delivery-status-guidelines.md).

- **Pick up.** Read the status record and take its next ticket, or the one the user names. Read the ticket, the tickets that block it, and the specification scope item it names. Do not start a ticket whose blockers are not done. Mark it in progress.
- **Requirement or specified behavior changes.** This includes a bug fix that changes behavior the specification states. Follow "Keeping it in sync" in [Specification guidelines](references/spec-guidelines.md) before changing the code.
- **A finding or issue is left for later.** Add it to the ticket that owns that behavior, or write a new ticket that names its scope item and blockers. Do not leave it only in the conversation.
- **Close.** When the work is merged, or handed back when there is no merge, and its acceptance criteria were verified, mark the ticket done and update the status record: the milestone, the blockers it cleared, and the next ticket. A ticket whose checks are not finished stays in progress.

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

A project that keeps these records in an older layout is migrated first: read [Legacy layout migration](references/legacy-layout-migration.md) and use `scripts/migrate_layout.py`.

Use existing documents and task systems that serve the purposes below. When no arrangement exists and full development handoff is needed, create the specification, `engineering/architecture.md`, `engineering/status.md`, ticket files, `AGENTS.md`, and the `CLAUDE.md` pointer. For a bounded architecture decision, select the records needed for the requested outcome.

| File or location | Purpose | When to create or update | When to read |
|---|---|---|---|
| `engineering/architecture.md` | Shared architecture, testing strategy, assumptions, and migration order across tickets | When shared technical decisions need to persist | Before changing the relevant architecture, testing strategy, or migrations |
| The existing specification, `openspec/specs/`, or `engineering/specs/<feature>.md` as the core's [Engineering Documents](../software-engineering-guidelines/SKILL.md#engineering-documents) sets | What is to be built: scope items, exclusions, flows, constraints and decisions | Before cutting tickets; first of all when a requirement changes | Before working on a ticket of that feature, and when checking the result against the request |
| `engineering/status.md` | Current progress, blockers, next verifiable output, and next ticket | When ongoing tracking or handoff is needed; update as relevant state changes | On arrival to pick up work |
| The existing ticket system, or `engineering/tickets/` as the core's [Engineering Documents](../software-engineering-guidelines/SKILL.md#engineering-documents) sets | Each ticket's deliverable, acceptance criteria, and blocking dependencies | When asked to break down work or prepare development handoff | Read the assigned ticket and its dependencies before implementation |
| `AGENTS.md` | Project working rules and the locations and reading triggers of supporting records | When establishing coordination or changing working rules | Before starting project work |
| `CLAUDE.md` | Entry point directing agents to `AGENTS.md` | When establishing the default coordination setup; keep actual rules in `AGENTS.md` | As an entry point to the project rules |


Read existing content before updating it, preserve unrelated sections, and register actual artifact paths with when they must be read. Keep shared technical decisions in the architecture record and per-ticket acceptance criteria on the owning ticket.

## Completion check

- The result answers the requested architecture or ticketing need.
- Engineering analysis covers feature flows, failures, interaction boundaries, testing, and applicable migration risks; ticketing work assigns every analyzed acceptance item an owner and records real blockers.
- Unresolved assumptions and decisions are explicit. Project-required validation and delivery rules are followed.
- Updated records retain unrelated content, link to the actual sources, and identify the next verifiable action when handing off.
