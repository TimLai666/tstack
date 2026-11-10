---
name: test-and-fix
description: "Run tests, find failures, fix them, verify. Diff-aware: tests affected behavior in web apps, APIs, CLIs, and libraries. This skill MUST be invoked on the triggers below, and SHOULD be invoked after any code change the user has not yet verified, before pushing, before marking a ticket or task as done, and before reporting that something is fixed. It MUST NOT be replaced by waiting for CI. Triggers on: 跑測試, 測一下, 有沒有壞掉, run tests, test this, 跑一下 tests, 測試, check if broken"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - AskUserQuestion
metadata:
  version: "1.6.1"
---

## Preamble

Read the user's requested test scope and commands, project instructions, test configuration, and relevant source files. Use the project's existing delivery or task records when they help establish the expected behavior.

Identify the target: web UI, API, command-line tool, library, or another artifact. Testing can run on the current branch, including the base branch. Inspect existing changes before editing.

## Phase 1 — Analyze what changed

Use the supplied scope first. When testing changes, inspect the relevant staged, unstaged, or committed diff and trace its callers and consumers. Determine the comparison ref from the task or repository configuration; fetch only when the comparison needs updated remote information.

Map the affected behavior:
- Web UI: pages, components, interactions, and rendered states.
- API: endpoints, authentication, inputs, responses, and errors.
- CLI: arguments, input/output, exit codes, and file effects.
- Library: public functions, callers, return values, and edge cases.

For tests requiring a running service, find the startup command and address in project configuration, documentation, or existing process output. Start the required local service within the task's authorization. Ask only for essential information that cannot be established from available evidence.

---

## Phase 2 — Build test plan

For each affected behavior, identify the expected result, test method, and priority. Include relevant normal, invalid-input, empty, and failure cases. Use the project's existing test commands and verification requirements, following the testing strategy in **software-engineering-guidelines**.

Cross-check the plan against the request and relevant task records. A mismatch is a reason to clarify the expected behavior, not to silently change the test scope.

---

## Phase 3 — Execute tests

Execute the Phase 2 plan using the selected tests. For web UI changes, inspect the affected rendering and interactions in the running application. Run the full suite according to project rules.

For each test:
- **Pass** — describe what was verified
- **Fail** — exact symptom and evidence
- **Unexpected** — anything unplanned

### What counts as verified

- **Test the deliverable itself.** Run the artifact the user will receive, in the runtime, operating system and client it will be used in. A simulation in another language, a stand-in window or process, a different operating system, or a different browser from the user's shows only that the stand-in works. When the real target cannot be run, report the behavior as unverified and name what is missing.
- **Run integration tests before pushing.** Use the project's local integration command. Waiting for CI does not replace this run and does not allow a ticket to be marked done. When the suite cannot start locally, check the environment with [investigate's common checks](../investigate/references/common-checks.md) before concluding it cannot run.
- **An intermittent failure is a finding.** Record the test name, how many runs failed out of how many, and the environment, then check timing once (waits for network or UI state, ordering, shared state). A rerun that passes does not close it.
- **Visual results need a rendered image that was looked at.** For UI, inspect the rendered screen. For documents such as docx or PDF, render the pages to images and inspect them; page counts, word counts and reading the markup do not establish layout. When no image could be produced or viewed, write「未視覺確認」in the report.
- **A reference number from the user must match.** When the result differs from it, state the gap and the candidate causes. Being in the same order of magnitude is not a match.

---

## Phase 4 — Fix loop

For each failure, locate the root cause first. If it cannot be established from the tested changes and evidence, invoke **investigate**.

1. Add or update the regression test required by the core's [Regression Tests](../software-engineering-guidelines/SKILL.md#regression-tests).
2. Make the minimal fix, then rerun the failing case and relevant regression checks.
3. Commit under the core's [Staging and Commits](../software-engineering-guidelines/SKILL.md#staging-and-commits).

Report verification gaps explicitly.

---

## Report

Levels follow the core's [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity).

```text
## Test Report [feature/branch] [date]

### Summary
Tests run: N | Passed: N | Failed: N | Fixed: N (with regression tests)

### Changes tested
- [target/behavior] — [result]

### Bugs found & fixed
1. [description] — file:line — regression test: [test name]

### Issues found (not yet fixed)
1. [P0-P3] [description] — blocking: [yes/no]

### Not verified
- [behavior] — [what was missing: real target, integration run, rendered image] — or 未視覺確認

### Regression tests added
- [test file]: [test names]

### Recommendation
[SHIP / FIX FIRST / INVESTIGATE]
```

---

## Test framework bootstrap (if no tests exist)

Check whether built-in language tools, existing scripts, or a small reproducible test can verify the behavior. Use a test framework when it adds necessary capability; explain the dependency and setup implications before introducing it, following the task's authorization.

A reproducible check must exercise the actual behavior and expose the bug without the fix. If verification remains blocked, report the missing capability rather than treating an unverified fix as complete. Follow the commit arrangement above; commit framework setup separately when using the default arrangement.
