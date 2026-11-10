# Engineering workflow

### Preamble

Confirm the project root and resolve project files from it, even when starting in a subdirectory. Locate the plan that matches the user's scope by its content and project references. `docs/plans/` and `*-plan.md` are discovery hints; the user may have chosen another location. Distinguish feature plans from status records rather than choosing by modification time.

Read the applicable project instructions, the selected plan, and existing architecture documents, including `ENG.md` or `ARCHITECTURE.md` when present. Read the full relevant sections and their dependencies before designing or updating them. A missing conventional filename does not establish that no equivalent document exists.

Inspect project configuration and documented workflows to establish the language, framework, database, deployment target, and ticket tooling. Verify required tool availability when relevant. Use source history when needed to resolve a decision or constraint. If a material choice remains unknown, ask with a recommendation.

If `delivery-plan.md` exists, read [Legacy status migration](legacy-status-migration.md) before updating status records.

Follow existing architecture documents, status tracking, and ticket tooling. When none exists and full development handoff is needed, use the default artifact set in Steps 4-5. For advice or a bounded architecture decision, deliver the requested analysis and update an existing decision record when appropriate. Do not create a parallel tracking system.

In Steps 4-5 and their references, default filenames stand for the corresponding project-selected destinations. Preserve their formats and register their actual paths. Use OpenSpec when established by project instructions; missing tooling is a limitation to resolve, not permission to silently change the workflow.

### Decisions

Follow the shared decision rules in SKILL.md. Collect unresolved tradeoffs during analysis and present related decisions together, with recommendations. Pause dependent work for decisions requiring user input; continue independent analysis.

### Step 1 — Per-feature pass

Take the feature list from the plan document — the scope items, each already phrased as something a person can do. Work them one at a time, in the order the plan gives, and finish one before opening the next. The whole-system picture is Step 2; it is assembled from what these passes decide, not drawn ahead of them.

No plan document, or a list still written by module? Fix that first — turn it into a feature list, preserving the agreed scope; confirm only unresolved scope choices, otherwise every pass below inherits the technical axis and the tickets come out layered.

For each feature, run 1a through 1e, then move to the next feature.

#### 1a — How this feature flows

Entry point, what it touches, where it stores, what states it moves through.

```text
[Browser] --POST /api/payment--> [PaymentController]
                                   validate inputs
                                   [PaymentService] --> [Stripe API: external]
                                   [DB: payments] success/failure
                                   [EmailWorker] --> [Email provider: external]
                             (async)

Trust boundaries: Browser -> PaymentController (untrusted client input);
PaymentService -> Stripe API and EmailWorker -> Email provider (external services).
Controller, service, worker, and payments DB are application-managed in this example.
State machine: pending -> processing -> succeeded | failed | refunded
```

Show the flow with the analysis. Record established decisions and flag unresolved choices under the shared decision rules.

#### 1b — Error/rescue map (mandatory)

For every operation in this feature that can fail:

| Operation | Exception/Error | Who catches it | What user sees | Tested? |
|-----------|-----------------|----------------|----------------|---------|
| Stripe charge | `Stripe::CardError` | PaymentService | "Card declined" + retry | Plan: yes |
| DB write | Connection timeout | ActiveRecord | 500 + alert | Plan: yes |
| Email send | SMTP failure | EmailWorker | Silent retry x3 | Plan: yes |

Anti-pattern: `rescue StandardError` or `catch Exception` is a code smell. Call it out.

#### 1c — Shadow paths

For each data flow in this feature, trace all four paths:
- happy path
- nil/null/undefined input
- empty/zero/blank input
- upstream error

For each shadow path: does the plan handle it? If not, flag it.

#### 1d — Interaction edge cases

| Interaction | Edge case | Expected behavior | Covered? |
|-------------|-----------|-------------------|----------|
| Form submit | Double-click | Debounce / idempotency key | ? |
| Long operation | User navigates away | Background job continues | ? |
| Any form | Session expires mid-fill | Graceful redirect, data preserved | ? |
| List view | 0 results | Empty state with CTA | ? |
| List view | 10,000+ results | Pagination enforced | ? |

Flag any `?` as a gap.

#### 1e — How this feature gets tested

A seam is a place where behavior can be swapped without editing the code under test — where the fakes get injected. Decide where this feature is tested before deciding what kinds of tests to write.

- Prefer existing seams to new ones, including one an earlier feature already chose. A seam that exists only to make testing possible is an architecture change, not a test decision.
- Take the highest seam that still reaches the behavior. High seams survive internal refactors; low seams go red when a private method moves.
- If a new seam is needed, propose it at the highest point possible.

Example — "place order, then send confirmation email":

| Seam | What gets faked | Cost |
|------|-----------------|------|
| `POST /orders` | Email sender | Survives every refactor below the controller |
| `OrderService.create` | Email sender, order repo | Breaks when the service interface moves |
| One spec per collaborator | Validator, pricing, template, SMTP | Four sets of fakes, all red on any internal rename |

Record the proposed seam and its rationale. Reuse established choices; raise a decision when a new seam changes architecture or an agreed approach. Mark new proposals provisional until Step 2b checks them across features.

#### Where the 1b-1d tables go

When ticketing is requested, assign each row to exactly one owning ticket in Step 5a as acceptance criteria. For architecture-only work, include the relevant analysis in the requested deliverable or existing decision record without creating tickets. Keep one authoritative copy and link to it from shared records when needed.

---

### Step 2 — Consolidate

Runs once, after every feature has been through Step 1.

#### 2a — Architecture diagram

Assemble the per-feature flows into one picture: entry points, data flow, state transitions, service boundaries, trust boundaries, storage. Same notation as 1a, all features on one canvas.

Present the consolidated diagram and record the resulting decisions. Ask about material unresolved tradeoffs or changes to an agreed approach.

This is where features that quietly disagree surface — two of them assuming different boundaries, different storage, or incompatible state names. Say which two, say what each assumed, and go back to the feature that has to give way. A confirmation that never sends anything back is theatre; the diagram earns its place by catching exactly this.

#### 2b — Collapse the seams

Compare the provisional seams from 1e. Share an existing seam where it preserves meaningful behavior coverage and reliable failure diagnosis. Keep separate seams where behavior boundaries, isolation, or test cost justify them; do not optimize for a fixed count.

Where several features can share one higher seam, propose the collapse and say which per-feature answers it overrides. Only ask again where collapsing contradicts something the user already chose; a seam that survives untouched needs no second confirmation.

#### 2c — Fill the test matrix

Two rules before writing a single row:

- Test external behavior only. A test that breaks when internals are rewritten but behavior is unchanged is testing the wrong thing.
- Find prior art. Locate existing tests of the same shape in the codebase and follow their structure instead of inventing a new one.

| Test type | What to cover | Priority |
|-----------|---------------|----------|
| Unit | Business rules and relevant decision boundaries | Based on failure impact |
| Integration | Changed DB/API contracts and failure handling | Based on failure impact |
| E2E | Critical user journeys and consequential failure paths | Based on workflow risk |
| Load | Workloads derived from expected demand, capacity assumptions, and performance targets | When capacity or latency risk warrants it |

Follow the project's testing rules. Explain coverage and workload choices using the changed behavior, failure impact, and performance goals; run the full suite according to project rules.

### Step 3 — Migration and deployment plan

If the change touches the database, locate its actual migration mechanism and read the migrations and conventions relevant to the change, including dependencies needed to understand their order and compatibility.

For each migration: reversible? locks tables? needs backfill? can run while old code is live?

### Step 4 — Record shared technical decisions

Use the project's existing architecture decision document. For the default full-handoff setup, write `ENG.md` to the project root. `ENG.md` is a **state file**: one per project, updated in place. Never date-stamp or branch-stamp the filename — git already provides version history and branch isolation, and a second copy would leave re-sync with no single target to read.

Keep shared architecture, testing strategy, standing assumptions, and migration order here. When tickets exist, keep path-specific acceptance criteria on their owning tickets and link to them. For architecture-only work, retain the requested analysis as described in the per-feature pass.

The next architecture review and agents changing these decisions read this record. Register its actual path and reading triggers in the project's coordination file during handoff (Step 5c).

**Read before writing.** If the selected architecture document exists, read it first and update the sections that changed. Do not regenerate from scratch — a re-sync that rewrites blind loses the prior run's seam decisions.

```markdown
# Engineering Plan: [project]
_[date] - eng-architect - [repo]:[branch]_

## Architecture
[ASCII diagram]

## Data flow
[Main flows, happy path]

## Test seams
[Chosen seam per flow, what gets faked, why this level]

## Test matrix
[Table]

## Migration plan
[If applicable]

## Hidden assumptions
- [assumption] - risk: [consequence]
```

The title names the project, not the feature. One file serves every feature in the repo, so a feature name in the heading goes stale the moment the next run touches it.

### Step 5 — Prepare development handoff

Apply this step when the request includes tickets or development handoff. Update the existing project system. With no established arrangement and a full handoff to prepare, create the complete default set below: `ENG.md`, `delivery-status.md`, tickets, `AGENTS.md`, and the `CLAUDE.md` pointer.

Locate the existing status and coordination records using project instructions and root-relative paths. Read the complete relevant content before updating it, preserve unrelated sections, and update the existing records in place. Verify a record is absent before creating one; a missing file in the current subdirectory or an unfamiliar filename is not sufficient evidence.

#### 5a — Cut the work into tickets

Read [references/ticket-breakdown-guidelines.md](ticket-breakdown-guidelines.md) before slicing anything.

Cut by what someone can do, not by which layer the code sits in. Each ticket is one narrow path through every layer it needs, verifiable on its own, labelled with its Epic and User Story, and declaring the tickets that block it. Shared foundations collapse into one ticket the others depend on; a wide refactor goes expand → migrate in batches → contract. Then run the coverage check: every row from the per-feature pass (1b-1d) gets exactly one owning ticket, and every story has at least one ticket.

Present the ticket set as a numbered list with title, blockers, and delivered behavior. Check granularity, real dependency gates, coverage, and opportunities to merge or split. Ask together about unresolved choices that affect scope, sequencing, or an agreed approach. If those choices are already settled and ticket creation is authorized, write the set without another approval round.

Tickets land where the Preamble established:

- **Plain markdown** — one file per ticket under `docs/tickets/`, numbered in dependency order. Use that directory as the backlog when handing off implementation.
- **OpenSpec** — one ticket is one change, never one task. Map each change to one milestone id in `delivery-status.md`; that milestone order carries the blocking edges, because OpenSpec has none between changes. Use the `openspec` skill for CLI commands, delta syntax, validation and archive flow if it is installed; if it is not, use the project's documented tooling when available. Otherwise report the missing capability and ask before switching an established ticket workflow; continue preparing the ticket content.

Keep dependency ordering in the chosen ticket system or its designated status record, not in `ENG.md`.

#### 5b — Create or update `delivery-status.md`

Read [references/delivery-status-guidelines.md](delivery-status-guidelines.md) before writing.

After the tickets and dependencies are established, select the next actionable ticket and update status. If none can start, record the blocker or completion state rather than inventing a next ticket. Use that reference as the single source for status sections, update rules, and handoff context. Link the actual architecture decision document and ticket location. In the default OpenSpec arrangement, milestone ordering records the cross-change blocking sequence.

#### 5c — Create or update `AGENTS.md` and `CLAUDE.md`

Read [references/agent-context-files.md](agent-context-files.md) first.

`AGENTS.md` must contain:
- required artifacts — name each one and say when to read it, not just that it exists
- handoff expectations
- planning discipline
- update rules
- project-specific constraints

Register actual artifact paths and when to read them. Default full-handoff example:

```md
## Required artifacts
- `ENG.md` — the project's standing technical decisions.
  Read it before changing architecture, picking a test seam, or writing a migration.
- `delivery-status.md` — where the project currently stands.
  Read it first on arrival.
- `docs/tickets/` (or `openspec/changes/`) — the tickets and their blocking edges.
  Pick up anything whose blockers are all done.
```

Keep the architecture record registered even when the status record also links it, so an agent starting from a single ticket knows when to read it.

**`AGENTS.md` is shared. Own your sections, leave the rest alone.** Other skills maintain their own sections in the same file and none of them announce themselves here:

| Section | Owner |
|---|---|
| The five items above | this skill |
| `## Follow-ups` | `software-engineering-guidelines` |
| `## Zeabur 部署規範` | `set-zeabur-conventions` |
| Anything else | the user, or a skill not listed here |

Update your own sections in place. Never delete or rewrite a section you do not own — an unfamiliar section is someone else's working state, not clutter. The "must not become a personal note file" rule below applies to the sections this skill owns, not to the whole file.

`CLAUDE.md` must contain only:

```md
Read `AGENTS.md` before doing any project work. Treat it as the project operating contract.
```

#### Convergence artifact contract

| Artifact | Must contain | Must not become |
|---|---|---|
| `delivery-status.md` | phase, blockers, next output, next ticket | roadmap copy or changelog dump |
| Tickets | one user-visible slice each, with its blocking edges | one ticket per layer, or one per phase |
| `ENG.md` | what holds across tickets: architecture, seams, assumptions, migration order | a second copy of anything that lives on a ticket |
| `AGENTS.md` | shared operating rules any agent follows on every turn, stated without rationale or change history | a personal note file, a project introduction, or a changelog |
| `CLAUDE.md` | pointer to `AGENTS.md` | a second full operating manual |

#### Re-sync cadence

Update affected records after:
- phase changes
- milestone status changes
- blocker appears or clears
- handoff to another agent

Read [references/handoff-and-feedback-loop.md](handoff-and-feedback-loop.md) for the expected loop.

#### Handoff checklist

Before handing off to another agent:
- [ ] State current phase
- [ ] State blocker or explicitly say none
- [ ] State next verifiable output
- [ ] State next ticket
- [ ] State decision delta since previous handoff
- [ ] Include source links for critical context
- [ ] Confirm `delivery-status.md` was updated
- [ ] Confirm `AGENTS.md` is current
- [ ] Confirm `CLAUDE.md` points to `AGENTS.md`

