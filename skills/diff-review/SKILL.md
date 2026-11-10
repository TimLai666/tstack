---
name: diff-review
description: "Review a code diff. This skill MUST be used when the user provides a diff or asks for a code, PR or MR review, and before substantial or high-risk code is committed, handed back, opened as a PR or MR, or merged. It MUST NOT be skipped because the diff is small. A diff this conversation wrote MUST go to an independent reviewer; only a small, low-risk change gets a lightweight self-review. It MUST hand security-relevant changes to security-scan and changed screens to ui-review, and it checks what a change could break elsewhere. It MUST NOT be used for changes limited to documentation, prose, images or formatting. Triggers on: 幫我 review, 看 diff, PR review, MR review, code review, 影響範圍, 看看程式有沒有問題"
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
  version: "4.0.1"
---

## Who reviews

This follows the core's [Independent Review](../software-engineering-guidelines/SKILL.md#independent-review).

| You are | Do |
|---|---|
| The main conversation, and it wrote or changed any part of the diff | Do not review. Follow [Dispatching the review](#dispatching-the-review), then [Final output](#final-output) |
| The main conversation, and the diff is a small, low-risk change of its own | Do a [lightweight review](#lightweight-review) yourself |
| The main conversation, and it had no part in the diff | Review it yourself with the sequence below |
| A reviewer dispatched for this diff | Review it yourself with the sequence below. Do not dispatch anyone, and leave the handoffs to the main conversation |

Small and low-risk is defined in the core's [Independent Review](../software-engineering-guidelines/SKILL.md#independent-review). For a diff, security-relevant means [Security handoff](#security-handoff) applies, and high-impact means the condition in [Adversarial review](#adversarial-review) holds.

### Lightweight review

Read the whole diff once against the request and the checks in [references/technical-review.md](references/technical-review.md) that apply to it, and run the [blast-radius check](references/blast-radius.md). Dispatch no one. When [UI handoff](#ui-handoff) applies, look at the changed screens yourself following **ui-review** and report it on the `UI handoff` line. Report with [Final output](#final-output) and state on the `Reviewed` line that it was a lightweight self-review.

---

## Dispatching the review

1. Establish the diff and its base as in [Establish review scope](#establish-review-scope).
2. Decide which reviews apply: the code review always, and the ones [Security handoff](#security-handoff) and [UI handoff](#ui-handoff) call for. Deciding this is not reviewing.
3. Load **agent-delegation** and dispatch one reviewer per review with the `review` task type, at the same time when more than one applies. Whether to continue an existing reviewer or start a new one follows its reuse rules: start reviewers so they can be resumed, and send a re-review back to the reviewer that reported the findings unless this review has to be isolated from that one. Each task states:
   - the original request and acceptance criteria, so the reviewer can check scope
   - how to obtain the diff: the base and the command, or the PR or MR
   - the skill file to follow, by absolute path: this file for the code review, the **security-scan** skill in diff mode, the **ui-review** skill for the changed screens
   - that no project file may be modified, that a reproduction script goes in a temporary directory outside the project, and that findings use the core's [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity) format
4. Add the [Adversarial review](#adversarial-review) when its condition holds.
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
2. **Review code:** Review the full diff with [references/technical-review.md](references/technical-review.md), which also covers the documentation and guidance the diff affects.
3. **Hand over:** When you are the main conversation, decide with [Security handoff](#security-handoff) and [UI handoff](#ui-handoff) whether the diff needs those reviews, and run each one that applies.

---

## Findings

Report in the format and scale of the core's [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity). For each finding, cite the file and line, describe the trigger and impact, and recommend a proportionate action. Refer to a secret as the core's [Secrets](../software-engineering-guidelines/SKILL.md#secrets) rule requires.

---

## Blast-radius check

Read [references/blast-radius.md](references/blast-radius.md) and run it in each of these cases: the user asks what a change could break or affect; a playbook step calls for it; the diff is a fix or a refactoring; the review is a lightweight self-review. In a dispatched review, the reviewer runs it and reports it with the findings.

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

## Adversarial review

Run it when the diff is large, spans multiple components, or affects high-impact behavior such as authentication, authorization, payments, sensitive data, migrations, concurrency, or critical user workflows. It has two parts, each done by a reviewer the main conversation dispatches through **agent-delegation**:

- **Breakage.** One more reviewer takes the side of a chaos engineer, with the prompt below as its task.
- **Security.** When [Security handoff](#security-handoff) applies, the **security-scan** reviewer takes the side of an attacker. Say so in its task; **security-scan** describes how.

```text
You are an adversarial reviewer. Review the established diff.

Think like a chaos engineer. Find ways this code will fail in production — not
style issues, not missing tests, actual breakage: wrong results, lost or corrupted
data, races, unhandled failures, resource exhaustion. Vulnerabilities are reviewed
separately; note one only if you run into it.

Apply the checks in this skill's references/technical-review.md independently.
Include file and line references, the failure trigger, evidence, and impact.
Give each CONFIRMED finding a level from P0 (must fix before merging) to P3
(minor). NEEDS INVESTIGATION concerns go in a separate section with missing
facts and verification steps. Do not classify uncertainty as a confirmed defect.

Never print the values of settings, tokens, passwords or keys, including in the
commands you run and their output. Report the key name and where it is stored.
```

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
- [P0-P3] [CONFIRMED] location - trigger, impact, description, recommended action - ran: | read: evidence

### Needs investigation
- [NEEDS INVESTIGATION] location - observed evidence, possible failure, missing fact, verification step

### Scope differences
- [include only when scope drift or missing requirements exist]
```

Include the `Adversarial review` line only when that review ran. Always include the `Security handoff` and `UI handoff` lines. If there are no confirmed findings, state `No confirmed findings.` Report any investigation concerns separately. Do not include empty sections.
