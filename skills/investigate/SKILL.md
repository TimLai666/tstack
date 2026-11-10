---
name: investigate
description: "Find the root cause of a failure before fixing it. This skill MUST be used when a bug's cause is unknown or the user asks for root-cause analysis, and SHOULD be used for unexplained failures, regressions, flaky behavior, a red CI pipeline, an error that recurs, or an expected result that never appeared. It MUST NOT treat an apparently obvious cause as confirmed without evidence. When evidence already establishes the cause, go to verification and repair without restarting the investigation, unless the task is only to find the cause. Triggers on: 根因調查, 為什麼會這樣, 壞掉了, 怎麼又, 還是不行, CI 紅燈, pipeline 失敗, failing, broken, flaky"
allowed-tools:
  - Bash
  - Read
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
metadata:
  version: "1.6.0"
---

## Core rule

**No fix without understanding the root cause.** Use verified evidence to explain how the cause produces the symptom. An apparently obvious cause still needs verification; an already established cause does not need a new round of hypotheses.

Claims in the investigation and its report follow the core's [Evidence for Claims](../software-engineering-guidelines/SKILL.md#evidence-for-claims): name the check behind every conclusion, and keep an unverified cause labeled as a hypothesis.

## Step 1 — Understand the symptom

Gather the following from the report, available logs, project configuration, and prior attempts. Ask only for missing information that materially affects the investigation:

- **Exact symptom:** verbatim error, wrong output, crash, or silent failure.
- **Reproduction:** reliable trigger, frequency, and conditions for intermittent failures.
- **Onset:** when it started and potentially related changes.
- **Environment:** where it occurs and relevant differences from working environments.
- **Prior attempts:** what was tested or changed and the observed results.

When the symptom matches a row in [references/common-checks.md](references/common-checks.md), run that row's check before forming hypotheses.

## Step 2 — Form hypotheses

Propose plausible causes supported by the available evidence. Rank them by evidential support and explain the uncertainty without inventing percentages or padding the list to a fixed count. For each hypothesis, identify a discriminating check:

```text
Hypothesis: [possible cause]
Evidence: [observations supporting it]
Would rule it out: [contradicting observation]
Next check: [how to obtain evidence that distinguishes it from alternatives]
```

Common categories:
- Wrong data assumptions: missing values, unexpected types, or shapes.
- State or timing: concurrency, stale caches, or operation ordering.
- Configuration or environment differences.
- Changed external dependencies or library behavior.
- Regression from a relevant source change.

A user's belief that an area cannot be at fault affects investigation priority, but does not itself rule out that area.

## Step 3 — Test hypotheses with minimal disruption

Prefer existing logs, a debugger, configuration inspection, and controlled reproductions. Choose checks by their ability to distinguish causes, cost, and operational impact.

When observation is insufficient, use a reversible diagnostic change within the authorized scope. Record what changed, preserve existing work, and remove temporary instrumentation or restore diagnostic-only dependency changes after the check. Retain a diagnostic change only when it is intentionally part of the agreed fix.

| Hypothesis | Example check |
|---|---|
| A value is missing | Inspect it at the relevant boundary with a debugger or temporary targeted logging |
| Operations race | Compare operation timing and state transitions in a controlled reproduction |
| Configuration differs | Compare only relevant settings; redact secrets and prefer presence or equality checks for sensitive values |
| Dependency behavior changed | Compare relevant versions in an isolated reproduction without changing the shared environment |

Inspect source history for changes tied to the affected behavior and symptom onset. Follow relevant evidence rather than a fixed number of commits or days. Record the outcome of each check and revise or eliminate hypotheses.

## Step 4 — Trace the data flow

Use the evidence to trace the affected path, checking hypotheses along the way:

```text
[Request/Event enters at: ]
  → [Layer 1] — state here: [what you found]
  → [Layer 2] — state here: [what you found]
  → [Where behavior diverges from expected] — state here: [what you found]
  → [Where the symptom manifests]
```

Identify the earliest verified point where actual behavior diverges from expected. Cite the exact file and line when applicable, explain how it causes the symptom, and continue tracing upstream until earlier causes are ruled out. Steps 2–4 can inform one another as new evidence appears.

## Step 5 — Fix the confirmed cause

Make the smallest change that addresses the verified root cause. Before editing, explain the cause and why the proposed change resolves it. Mention related unresolved problems only when they affect the user's outcome or the scope of this fix.

Add the regression test required by the core's [Regression Tests](../software-engineering-guidelines/SKILL.md#regression-tests). Commit under [Staging and Commits](../software-engineering-guidelines/SKILL.md#staging-and-commits).

## Step 6 — Verify

Repeat the original reproduction with the fix and verify the regression coverage before and after it. Run relevant checks for affected behavior and follow the project's full-suite rules. Confirm temporary diagnostic changes have been cleaned up or intentionally retained.

If the symptom persists, use the observed result to revisit the hypothesis and data flow. Another fix attempt needs what the core's [Evidence for Claims](../software-engineering-guidelines/SKILL.md#evidence-for-claims) requires of a retry; otherwise go to Step 7.

## Step 7 — Stop or request help when evidence cannot advance

Pause affected repair attempts when the next one fails that same requirement, repeats a disproven guess, or needs unavailable information, access, expertise, or authorization. Continue independent investigation that can safely produce new evidence.

Report the actual blocker and a concrete next step:

```text
Blocked investigation: [what cannot currently be established]

Attempts and observations:
- [check or fix attempted, what changed, and observed result]

Current understanding:
[confirmed facts, remaining hypotheses, and what is uncertain]

Missing evidence or access:
[what is needed to distinguish the remaining causes]

Recommended next step:
[specific check, information request, or authorized action]
```
