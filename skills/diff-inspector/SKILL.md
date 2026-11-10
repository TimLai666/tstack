---
name: diff-inspector
description: "Inspect code diffs before opening a pull request or merging. This skill MUST be used when the user provides a code diff, pastes code changes, asks for a code or PR review, or when code is about to be submitted as a PR or merged. It MUST NOT be skipped solely because the diff is small. It SHOULD also be used before committing or handing back substantial or high-risk code changes. It MUST NOT be used when changes are limited to non-code content such as documentation, prose, images, or formatting. For small, low-risk self-changes, perform only a lightweight review without specialist dispatch. Checks requirement scope, correctness, compatibility, maintainability, and test coverage. Vulnerabilities are not reviewed here: when the diff touches security-relevant code, it MUST hand that part to security-scan in diff mode. Triggers on: 幫我看程式 diff, 看一下程式改了什麼, review 程式碼, PR review, diff review, code review, 看看程式有沒有問題"
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
  version: "2.0.0"
---

## Review timing

Review before opening a pull request and before merging. Reuse the previous result if the relevant diff has not changed; otherwise review again.

---

## Establish review scope

Identify the relevant code diff from the user's input, current worktree, pull request, or merge target. Inspect the repository's existing Git state, conventions, and task context as needed. If the review scope or base remains unclear after inspection, ask the user.

---

## Review sequence

1. **Check scope:** Compare the diff with the stated request and report meaningful scope drift or missing requirements.
2. **Review code:** Review the full diff using the technical checks below.
3. **Hand over security:** Decide with the rule in [Security handoff](#security-handoff) whether the diff needs a security check, and run it when it does.

---

## Technical review

Review the full diff. For each applicable area, verify:

- **Queries and data integrity:** Queries remain bounded, return the intended rows, and preserve data integrity across writes and transactions.
- **Race conditions and state:** Concurrent operations, check-then-act flows, shared state, and asynchronous work remain atomic and consistent.
- **Error handling:** Failures are surfaced and handled, including partial failures, timeouts, cleanup, and recovery.
- **Performance and resources:** Check unbounded work, resource leaks, N+1 queries, missing indexes, avoidable quadratic work, expensive loops, heavy dependencies, and fetch waterfalls.
- **Maintainability:** Check unnecessary complexity, duplicated logic, unclear responsibilities, leaky abstractions, and difficulty understanding, testing, or extending the change.
- **Data migration:** Check irreversible migrations, locking schema changes, missing foreign-key indexes, unsafe backfills, and removal of schemas before dependent code.
- **Completeness and compatibility:** For each changed shared contract, such as a state, field, path, identifier, schema, or configuration:
  1. Inventory relevant occurrences first: search the entire target tree using stable contract fragments such as path prefixes, filename patterns, field names, command names, or resolver functions.
  2. Trace each producer to all consumers and each consumer back to a concrete producer, including unchanged files outside the diff. A consumer has a concrete producer only when it computes the value or calls a named shared resolver. Prose placeholders, examples, and state expected from an earlier tool do not count.
  3. Compare the exact values or derivation logic used on both sides. Report unaccounted occurrences, missing implementations, and duplicated or divergent derivations.
- **API contracts:** Check incompatible responses, new required inputs without defaults, changed error formats, and pagination behavior using the compatibility tracing above.
- **Tests:** Tests demonstrate changed public behavior, negative and edge cases, failure paths, and regression protection. Check isolation violations and flaky patterns.

### Evidence and severity

Put an issue in Findings only when relevant code or observed behavior confirms a concrete failure scenario. Put evidence-backed concerns with missing decisive facts in a separate Needs investigation section, naming the missing fact and how to verify it.

- **P0:** Critical or blocking. Can cause data loss, a service outage, a security breach reported by the security handoff, or another failure that must be fixed before merging.
- **P1:** Serious. Likely to cause incorrect behavior or a major regression and should normally be fixed before merging.
- **P2:** Moderate and localized. Actionable, but may be scheduled after merging when the risk is acceptable.

For each finding:

- cite the relevant file and line; for a secret, cite its key name and location, never its value
- describe the trigger and impact
- assign P0, P1, or P2 based on impact
- label it `CONFIRMED`
- recommend a proportionate action

Do not report speculation or style preferences as defects.

Finding format: `[P0/P1/P2] [CONFIRMED] file:line - trigger, impact, description, and recommended action`

Investigation format: `[NEEDS INVESTIGATION] file:line - observed evidence, possible failure, missing fact, and verification step`. Describe impact conditionally rather than assigning a confirmed defect severity.

---

## Security handoff

This skill does not look for vulnerabilities. Run **security-scan** in diff mode on the same diff when it adds or changes any of the following:

- handling of input from outside the process: requests, uploads, files, messages, webhooks, command-line arguments, model output
- authentication, sessions, authorization, ownership or tenant checks
- queries, commands, templates, file paths or outbound requests built from variable data
- secrets, cryptography, tokens or random values used for security
- dependencies, lockfiles, CI/CD, container or deployment configuration

State which of these the diff touches, or that it touches none, with the files that decided it. When unsure, hand over.

Merge the returned findings into Findings using this mapping: 嚴重 to P0, 高 to P1, 中 and 低 to P2. Keep its evidence and location, and mark each as `security-scan`. If **security-scan** is not installed, say that the diff has security-relevant changes that were not reviewed, and list them under Needs investigation.

---

## Adversarial subagent

Run an adversarial subagent when the diff is large, spans multiple components, or affects high-impact behavior such as authentication, authorization, payments, sensitive data, migrations, concurrency, or critical user workflows.

```text
You are an adversarial reviewer. Review the established diff.

Think like a chaos engineer. Find ways this code will fail in production — not
style issues, not missing tests, actual breakage: wrong results, lost or corrupted
data, races, unhandled failures, resource exhaustion. Vulnerabilities are reviewed
separately; note one only if you run into it.

Apply the relevant Technical review checks from this skill independently.
Include file and line references, the failure trigger, evidence, and impact.
Use the Evidence and severity rules: CONFIRMED findings receive P0/P1/P2;
NEEDS INVESTIGATION concerns go in a separate section with missing facts
and verification steps. Do not classify uncertainty as a confirmed defect.

Never print the values of settings, tokens, passwords or keys, including in the
commands you run and their output. Report the key name and where it is stored.
```

---

## Documentation and guidance consistency

Review documentation and distributable guidance affected by the diff, both at the repository root and within affected packages, modules, or subtrees. Include, where applicable:

- README files, architecture guides, contributing guides, API references, and other explanatory documentation
- Package- or module-specific documentation
- Changelogs and release notes when required by project convention or when the change affects users
- Repository operating contracts for agents working in the repository, such as `AGENTS.md` or `CLAUDE.md`
- Installable agent skills, prompts, templates, examples, plugin metadata, and other agent-facing artifacts distributed by the repository

Check whether changes to behavior, interfaces, setup, configuration, installation, migrations, required artifacts, workflows, handoff rules, tool usage, or deployment constraints are reflected in every affected document or artifact.

When the repository distributes installable skills or other agent-facing artifacts, treat them as product outputs. Verify that their instructions, examples, references, metadata, and packaging remain aligned with the changed behavior.

Report each mismatch with references to both the changed code and the affected document or artifact.

---

## Final output

Lead with confirmed findings ordered from P0 to P2, followed by evidence-backed concerns needing investigation. Review and deduplicate results from technical, documentation, adversarial, and security-handoff checks by failure scenario and affected location, preserving distinct causes and the strongest evidence.

Use this structure:

```text
## Diff Inspector
Scope: [CLEAN / DRIFT / MISSING]
Reviewed: [diff source and scope]
Adversarial review: [RUN — Trigger: reason]
Security handoff: [RUN — touches: ... / NOT NEEDED — reason / NOT REVIEWED — security-scan unavailable]

### Findings
- [P0/P1/P2] [CONFIRMED] file:line - trigger, impact, description, and recommended action

### Needs investigation
- [NEEDS INVESTIGATION] file:line - observed evidence, possible failure, missing fact, and verification step

### Scope differences
- [include only when scope drift or missing requirements exist]
```

Include the `Adversarial review` line only when that review ran. Always include the `Security handoff` line. If there are no confirmed findings, state `No confirmed findings.` Report any investigation concerns separately. Do not include empty sections.
