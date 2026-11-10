# Delivery Status Guidelines

Use the project's established status record as the handoff entry point; `delivery-status.md` is the default when none exists and full handoff is needed. Preserve the existing format while covering the relevant state and source links below. A new agent should be able to read it first and know what state the project is in, what is blocked, and which ticket to pick up next.

## Required Sections

Use headings close to this shape:

```md
# Delivery Status

## Current Phase
## Stage Objective
## Active Workstreams
## Milestones
## Current Blockers
## Next Verifiable Output
## Next Ticket
## Decision Log
## Source Links
## Handoff Notes
```

## Section Rules

### `Current Phase`
- Name the phase in one line.
- Avoid vague labels like `doing stuff` or `iteration`.

### `Stage Objective`
- State the outcome for the current stage, not the entire product vision.
- Make it specific enough to verify.

### `Active Workstreams`
- Keep this short.
- Point each workstream toward one concrete result.

### `Milestones`
- Track major checkpoints for the current stage.
- Use fields: `id`, `target`, `owner`, `status`, `verification_signal`.
- Keep status values explicit, for example: `not_started`, `in_progress`, `blocked`, `done`.

### `Current Blockers`
- List only active blockers.
- If none exist, say `None`.

### `Next Verifiable Output`
- Name the next artifact, behavior, or proof point that can be checked.
- Prefer outputs such as a merged capability, validated proposal, passing scenario, or reviewed document.

### `Next Ticket`
- Name one actionable next ticket id. If no ticket can start, state the blocker; if work is complete, say so rather than inventing another ticket.
- This is the default pickup point for the next agent.
- In OpenSpec mode the ticket id is the change id.

### `Decision Log`
- Record key decisions that affect implementation or sequencing.
- Use fields: `decision`, `rationale`, `timestamp`, `impacted_ticket_ids`.
- Record deltas only; do not duplicate unchanged history.

### `Source Links`
- Link the actual architecture decision document (`ENG.md` in the default setup), so the next agent can find architecture, testing decisions, and standing assumptions.
- Then link the plan document, and the ticket directory or change directory.
- Add the other primary sources needed to reconstruct context quickly: thread, document, issue, or PR.
- Prefer stable links and concise labels over raw dump content.

### `Handoff Notes`
- Capture only the minimum context needed to continue.
- Summarize current constraints and active caveats, not the full transcript.

## Update Cadence

Update `delivery-status.md` when:
- the phase changes
- a milestone status changes
- the next verifiable output changes
- a blocker appears or clears
- the recommended next ticket changes
- a logged decision changes sequencing or scope
- source links needed for continuity change
- a handoff is about to occur

## Quality Checks

- A new agent can answer "where are we, what is blocked, what do I do next?" after one scan.
- The file points to the next ticket directly.
- Milestone status is current and tied to verifiable signals.
- Critical decisions are recoverable from `Decision Log` plus `Source Links`.
- Source links reach the actual architecture and testing decisions.
- The file is shorter than the chat history it replaces.
- The file does not try to serve roadmap, launch, and handoff purposes at the same time.
