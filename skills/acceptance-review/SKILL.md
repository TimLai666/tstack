---
name: acceptance-review
description: "Check finished work against what was originally asked: every requirement is matched to a result that was actually exercised, and the original problem is shown to be solved. This skill MUST be used before reporting substantial work as done or handing it back, and when the user asks whether the result meets the request. Work this conversation produced MUST be checked by an independent reviewer who is not given the implementer's summary. It MUST NOT replace diff-review, security-scan or test-and-fix. Triggers on: 驗收、有沒有做到、有沒有符合需求、有沒有解決問題、做完了嗎、acceptance review"
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Agent
  - AskUserQuestion
metadata:
  version: "1.0.1"
---

## Overview

Answer one question: does what was delivered do what was asked? The answer comes from the delivered result, not from a diff, so this review applies with or without a PR. The reviewer starts from the request, goes to the running result, and reports every requirement that has no working result behind it.

| Review of | Skill |
|---|---|
| The result against the original request | this skill |
| Code logic and implementation | **diff-review** |
| Vulnerabilities | **security-scan** |
| Rendered screens | **ui-review** |

Tests that pass and a diff that reads well do not answer this question. Code can be correct and still leave out half of what was asked.

## Who reviews

This follows the core's [Independent Review](../software-engineering-guidelines/SKILL.md#independent-review).

| You are | Do |
|---|---|
| The main conversation, and it produced any part of the work | Do not review. Follow [Dispatching the review](#dispatching-the-review) |
| The main conversation, and it had no part in the work | Review it yourself from Step 1 |
| A reviewer dispatched for this work | Review it yourself from Step 1. Do not dispatch anyone |

## Dispatching the review

Load **agent-delegation** and dispatch one reviewer, following its reuse rules. Use the `acceptance` task type: the reviewer has to run the result, and a result often writes something, so this type gives the reviewer a sandbox directory outside the project and keeps the project's files read-only. The task states:

- **The request in the user's own words.** Quote the original message, and every later message in which the user corrected, added to or narrowed it. Do not paraphrase and do not merge them into a tidy list.
- **The agreed acceptance criteria**, when some were set.
- **Where the result is and how to run or open it**: the commands, the address, the files, the test accounts or sample data it needs.
- **This file's absolute path** as the procedure to follow.
- **Where the result may write.** Point output paths, databases and generated files at the sandbox directory or at a local or test environment. No project file may be modified.

Leave out the implementer's summary, the list of what was done, and any statement that something works. The reviewer finds out what was delivered by looking at it.

When the reviewer returns, check each finding against the result. Fixing a finding is implementation again: the fixed work goes back to the reviewer, normally the same one resumed.

## Step 1 — List what was asked

Build the list from the quoted messages only.

- One row for each thing the user asked for, in their words, with the message it came from.
- A later message that corrects or narrows an earlier one replaces it. Keep the latest version and note what it replaced.
- Keep requirements that the request implies but does not spell out in a separate group, marked as implied. This covers the core's [Counterpart Operations](../software-engineering-guidelines/SKILL.md#counterpart-operations) for every requested action, and the states a requested screen cannot avoid, such as empty and error.
- When a requirement can be read in more than one way, list the readings. Do not pick one.

## Step 2 — Find and exercise the result for each row

For each row, locate what was delivered and use it the way the user would: run the command, call the endpoint, open the screen and perform the action, read the produced file. Let it write only where the task allows. When exercising a row would write to a real external system that has no test environment, do not do it: the row is not verifiable, and the report says what is missing.

| Verdict | When |
|---|---|
| Met | The result was exercised and does what the row says |
| Partly met | Some of it works; name the part that does not |
| Not met | Nothing delivered does this, or what is there does not work |
| Not verifiable | It could not be exercised; name what was missing |

Reading the code, the diff or a test name is not exercising the result. A row whose only evidence is that kind stays not verifiable.

## Step 3 — Check the original problem is gone

When the request was to fix or change something that was wrong, reproduce the original situation from start to finish and observe that it now behaves as asked. A fix that passes its own new test while the user's original scenario still fails is not met.

## Step 4 — Look for what was delivered instead

- Something different from what was asked, presented as if it were the request.
- Placeholders, sample or hard-coded data, stubs, disabled paths and "to be done later" notes inside what is presented as finished.
- Requirements dropped without the user having agreed.
- Work beyond the request that changes behavior the user did not ask to change.

## Step 5 — Report

Give the requirement table first, then the findings in the format and scale of the core's [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity), with the requirement and where it was exercised as the location.

| Level | Against the request |
|---|---|
| P0 | The main thing that was asked for is not delivered or does not work, or the original problem is still there |
| P1 | A stated requirement is not met or only partly met |
| P2 | An implied requirement is not met, or delivered work changes something that was not asked |
| P3 | A small deviation from the wording of the request that does not change what the user can do |

```text
## Acceptance Review
Request: [one line naming it, and the messages it was built from]
Exercised: [how the result was run or opened]

| # | Asked (source) | Verdict | Evidence |
|---|---|---|---|

### Findings
- [P0-P3] [CONFIRMED] requirement # and where - trigger, impact, description, recommended action

### Needs investigation
- [NEEDS INVESTIGATION] requirement # - observed evidence, possible failure, missing fact, verification step

### Open readings
- [requirement #] - the readings, and which one the result follows
```

Rows that are not verifiable go under Needs investigation with what is missing. Omit a section that has nothing in it. State plainly when every row is met.

## Completion check

- Every row came from the user's own messages, and each has a verdict backed by something that was run, opened or read as output.
- The original scenario was reproduced when the request was a fix.
- Nothing is reported as met on the strength of code, a diff, a test name or the implementer's word.
- The work is reported to the user as done only when no P0 or P1 finding is open; open findings are named in the report.
