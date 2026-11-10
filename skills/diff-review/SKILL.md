---
name: diff-review
description: "Review a code diff before substantial or high-risk code is committed or handed back, opened as a pull request or merge request, or merged. This skill MUST be used when the user provides a code diff, pastes code changes, or asks for a code, PR or MR review, and when code is about to be submitted as a PR or MR or merged. It MUST NOT be skipped solely because the diff is small. When this conversation wrote any part of the diff, the review MUST be dispatched to an independent reviewer through agent-delegation, not done by the main conversation. It MUST NOT be used for changes limited to documentation, prose, images or formatting. It checks requirement scope, correctness, compatibility, maintainability and test coverage, and is the single entry for review: it MUST hand security-relevant changes to security-scan and changed screens to ui-review, and merges their findings. Triggers on: 幫我 review, 幫我看程式 diff, 看一下程式改了什麼, review 程式碼, PR review, MR review, diff review, code review, 看看程式有沒有問題"
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
  version: "3.1.2"
---

## Who reviews

This follows the core's [Independent Review](../software-engineering-guidelines/SKILL.md#independent-review).

| You are | Do |
|---|---|
| The main conversation, and it wrote or changed any part of the diff | Do not review. Follow [Dispatching the review](#dispatching-the-review), then [Final output](#final-output) |
| The main conversation, and it had no part in the diff | Review it yourself with the sequence below |
| A reviewer dispatched for this diff | Review it yourself with the sequence below. Do not dispatch anyone, and leave the handoffs to the main conversation |

---

## Dispatching the review

1. Establish the diff and its base as in [Establish review scope](#establish-review-scope).
2. Decide which reviews apply: the code review always, and the ones [Security handoff](#security-handoff) and [UI handoff](#ui-handoff) call for. Deciding this is not reviewing.
3. Load **agent-delegation** and dispatch one reviewer per review with the `review` task type, at the same time when more than one applies. Whether to continue an existing reviewer or start a new one follows its reuse rules: start reviewers so they can be resumed, and send a re-review back to the reviewer that reported the findings unless this review has to be isolated from that one. Each task states:
   - the original request and acceptance criteria, so the reviewer can check scope
   - how to obtain the diff: the base and the command, or the PR or MR
   - the skill file to follow, by absolute path: this file for the code review, the **security-scan** skill in diff mode, the **ui-review** skill for the changed screens
   - that no file may be modified, and that findings use the core's [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity) format
4. Add the reviewer described in [Adversarial subagent](#adversarial-subagent) when its condition holds.
5. When the reviewers return, check each finding against the code or the rendered result. Keep what holds, and move what cannot be confirmed to Needs investigation with the missing fact.

Fixing the findings is implementation again. A diff that changed after review is reviewed again by a reviewer, normally the same one resumed, not by the main conversation.

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
3. **Hand over:** When you are the main conversation, decide with [Security handoff](#security-handoff) and [UI handoff](#ui-handoff) whether the diff needs those reviews, and run each one that applies.

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

### Findings

Report in the format and scale of the core's [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity). For each finding, cite the file and line, describe the trigger and impact, and recommend a proportionate action. Refer to a secret as the core's [Secrets](../software-engineering-guidelines/SKILL.md#secrets) rule requires.

---

## Security handoff

This skill does not look for vulnerabilities. Run **security-scan** in diff mode on the same diff when it adds or changes any of the following:

- handling of input from outside the process: requests, uploads, files, messages, webhooks, command-line arguments, model output
- authentication, sessions, authorization, ownership or tenant checks
- queries, commands, templates, file paths or outbound requests built from variable data
- secrets, cryptography, tokens or random values used for security
- dependencies, lockfiles, CI/CD, container or deployment configuration

State which of these the diff touches, or that it touches none, with the files that decided it. When unsure, hand over.

Merge the returned findings into Findings, keeping their level, evidence and location, and mark each as `security-scan`.

---

## UI handoff

This skill does not judge how screens look or behave. Run **ui-review** on the affected screens when the diff adds or changes what a user sees: templates, components, styles, layout, copy, or the empty, loading and error states of a screen.

State which screens the diff changes, or that it changes none, with the files that decided it. Merge the returned findings into Findings, keeping their level, evidence and location, and mark each as `ui-review`.

---

## Adversarial subagent

The main conversation dispatches one more reviewer through **agent-delegation**, with the prompt below as its task, when the diff is large, spans multiple components, or affects high-impact behavior such as authentication, authorization, payments, sensitive data, migrations, concurrency, or critical user workflows.

```text
You are an adversarial reviewer. Review the established diff.

Think like a chaos engineer. Find ways this code will fail in production — not
style issues, not missing tests, actual breakage: wrong results, lost or corrupted
data, races, unhandled failures, resource exhaustion. Vulnerabilities are reviewed
separately; note one only if you run into it.

Apply the relevant Technical review checks from this skill independently.
Include file and line references, the failure trigger, evidence, and impact.
Give each CONFIRMED finding a level from P0 (must fix before merging) to P3
(minor). NEEDS INVESTIGATION concerns go in a separate section with missing
facts and verification steps. Do not classify uncertainty as a confirmed defect.

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

Lead with confirmed findings ordered from P0 to P3, followed by evidence-backed concerns needing investigation. Review and deduplicate results from technical, documentation, adversarial, and handoff checks by failure scenario and affected location, preserving distinct causes and the strongest evidence.

Use this structure:

```text
## Diff Review
Scope: [CLEAN / DRIFT / MISSING]
Reviewed: [diff source and scope]
Adversarial review: [RUN — Trigger: reason]
Security handoff: [RUN — touches: ... / NOT NEEDED — reason]
UI handoff: [RUN — screens: ... / NOT NEEDED — reason]

### Findings
- [P0-P3] [CONFIRMED] location - trigger, impact, description, recommended action

### Needs investigation
- [NEEDS INVESTIGATION] location - observed evidence, possible failure, missing fact, verification step

### Scope differences
- [include only when scope drift or missing requirements exist]
```

Include the `Adversarial review` line only when that review ran. Always include the `Security handoff` and `UI handoff` lines. If there are no confirmed findings, state `No confirmed findings.` Report any investigation concerns separately. Do not include empty sections.
