---
name: software-engineering-guidelines
description: "The core of tstack and the guidelines for any software change. It names which tstack skill to use at each point of the work, gives the step list for each kind of task, and owns the rules the other skills share. This skill MUST be loaded before planning, designing, writing or changing code, reviewing, testing, shipping, or creating a Git commit (including a standalone commit request), and MUST NOT be skipped because the change is a one-liner. Triggers on: 寫 code, 改 code, 做功能, 修 bug, refactor, 重構, 開發, 實作, 寫程式, 架構設計, 需求釐清, code review, 測試, commit, init, 初始化專案, 建立 AGENTS.md, 建立 CLAUDE.md"
metadata:
  version: "3.1.0"
---

## The Stack

tstack is installed as a whole. At each point of the work in this table, load the named skill; do not work from memory of what it says.

| When | Use |
|---|---|
| Starting work in a project without its memory in context; when the work wraps up or something costly was learned; the user states a preference for every project; a fact about this machine or a remote host was found; before working on a remote host | **project-memory** |
| Architecture, module boundaries or the split into tickets is undecided | **eng-architect** |
| A failure whose cause is unknown, a red CI pipeline, the same error a second time, or an expected result that never appeared | **investigate** |
| Code changed and not yet verified; before pushing; before calling something fixed or done | **test-and-fix** |
| Substantial or high-risk code is about to be committed or handed back, opened as a PR or MR, or merged; the user hands over a diff | **diff-review**, which hands security-relevant changes to **security-scan** and changed screens to **ui-review** |
| A review of built screens is requested on its own | **ui-review** |
| The user asks what a change could break elsewhere | **diff-review**, with its blast-radius check |
| Substantial work is about to be reported as done or handed back; the user asks whether the result meets the request | **acceptance-review** |
| A security scan or hardening of the project is requested | **security-scan** |
| Pushing, opening or updating a PR or MR, merging | **ship-it** |
| The same kind of mistake happened a second time; the user asks to turn a rule into a check | **prevent-recurrence** |
| Dispatching a subagent or another CLI; changing an existing API's name, signature, usage or behavior; delivering a specification, article or report | **agent-delegation** |

## Playbooks

Every task follows a playbook: an ordered list of steps for that kind of task. At the start of a task, open [references/playbooks.md](references/playbooks.md), pick the one that matches (Feature, Bug fix, Refactoring, Investigation or Small change), and copy its steps into the task list word for word. A step that does not apply stays in the list as `skip: <reason>`.

## Core Principles

Read the reference named under each principle at the point it describes.

### 1. Think Before Coding

**Verify what you can. Make material assumptions and tradeoffs clear.**

- Own the implementation design. Resolve routine details from the code, documentation, existing conventions and focused checks; do not turn design work into a questionnaire.
- Ask the user only when a gap remains after checking and would materially affect the result, scope, authorization or an important tradeoff. Give a recommendation, and continue independent work meanwhile.
- Work out a coherent design for the full authorized outcome before filling components, and choose the simplest approach that satisfies all agreed requirements. If a simpler approach exists, say so. Push back when warranted.

Before designing anything larger than a single-location change, read [references/design.md](references/design.md).

### 2. Simplicity First

**Simple, correct implementations for the full agreed requirements. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- When the goal can be met either by removing code or by adding code, remove code. The removal stays within the task's scope and keeps every other behavior intact.
- Use concise, maintainable implementations. Do not rewrite accepted code solely to reduce line count while required outcomes remain incomplete.

If a senior engineer would call it overcomplicated, simplify.

### 3. Complete, Surgical Changes

**Touch everything the task needs and nothing else. Clean up only your own mess.**

- Finish the full authorized outcome in the turn: implementation, integration, verification and necessary repairs. Do not hold required work back for a later turn. When a real blocker prevents completion, finish what is independent of it and report the exact remaining gap. A feature covers every layer, entry point and edge case it needs. A fix covers the root cause, every occurrence of the same pattern and the related edge cases.
- Don't "improve" adjacent code, comments or formatting, refactor what is not broken, or delete pre-existing dead code. Match the existing style. Remove what your own change made unused.
- Mention out-of-scope issues you find and record them in the project's follow-up location.
- Write and change files with the editing tools. Content that spans lines or contains non-ASCII characters, quotes or backslashes does not go through shell quoting or a heredoc.

Every changed line traces directly to the user's request.

Read [references/changing-code.md](references/changing-code.md) before any of these: scripting a change, or overwriting, restoring or discarding a file; recording a follow-up; creating a repository or its `.gitattributes`; writing documents, rules, prompts or skills; creating or editing `AGENTS.md` or `CLAUDE.md`.

### 4. Testing Strategy (Test-First + scoped TDD)

**Choose verification that demonstrates the change works and matches its impact.**

- Every behavior-changing change needs test coverage. A change to text, formatting or documentation gets a check suited to that content. Run the full suite according to the project's rules, and the linter and type checker when the project has them. Unresolved failures mean verification is incomplete.
- A large change, a broad-scope change or a major new feature MUST be done test-first: write the failing test, then implement. It is large when it touches several modules or layers, changes a public boundary such as an API contract, data model, access rule or core flow, or adds a core feature or reworks a high-risk path (payment, authentication, permissions, data migration, state transitions).
- Before a check writes to an external system, confirm that a test environment exists and how the written data will be removed. With neither, do not write to it for verification; ask the user how to verify.
- Don't weaken a test just to make it pass, unless the test itself is wrong.

Read [references/testing.md](references/testing.md) when choosing the timing of tests for a small fix, before refactoring, and before editing skills, prompts or agent workflows.

### 5. Goal-Driven Execution

**Define success criteria. Use observed progress to choose each next step.**

- Turn the task into verifiable goals, and for multi-step work state each step with its check.
- In multi-part work, choose the next work from the primary flows that are still unimplemented or unverified before deepening a part that already works.
- Before a second attempt at something that failed, and when the work is a series of experiments, read [references/iterations.md](references/iterations.md).

#### Skeleton First

Before filling in logic for a new project, feature, or fix, write a skeleton that fixes the scope:

- New project or feature: code that runs end to end, with entry points, data shapes, and empty slots. Give each slot its signature (inputs, outputs, how errors are reported) and a list of expected results, including edge cases. Add two or three end-to-end acceptance flows that exercise the whole path.
- Fix: the root cause, the full list of places to change, and the check that proves each one.
- Include pseudocode only when it is already worked out.
- Place independent slots in separate files.
- Scale the skeleton to the task. A single-location change needs only its expected results and check.

Fill the slots until their checks and the acceptance flows pass. Decide, slot by slot, who fills it, by the amount of work:

- Dispatch a slot through **agent-delegation** when filling it is sizable: more than about a screenful of logic, several independent slots that can be filled at the same time, or bulk repetitive edits. The agent that fills a slot does not edit its checks.
- Fill a slot yourself when it is short enough that briefing and reviewing would cost more than writing it, or when you cannot yet say exactly what it has to do.
- Say in the report which slots were dispatched and which were not, with the reason.

## Shared Conventions

### Evidence for Claims

- Before concluding that something is impossible, absent, not installed, unsupported, or already confirmed, name the check that was run and the scope it covered. A timeout, a redirect, an empty result and a single failed lookup are not such checks.
- A cause that is not verified is a hypothesis. Label it as one, and do not write it into code comments, docstrings, agent instruction files, skills or project memory as a fact.
- A retry needs new evidence, a changed condition or a distinct diagnostic check. Without one, stop repeating the attempt and continue independent work. Do not stop only because some number of attempts failed, and do not change the acceptance criteria to make an attempt pass.

### Counterpart Operations

A requested action brings its counterparts with it. For each feature, go through: create, edit and delete; the reverse of every action (add and remove, increase and decrease, lock and unlock); ordering; the settings or entry point from which it is reached; where its data is stored; import and export; the edit history. Each one is either in scope or named as out of scope.

### Regression Tests

Every bug fix has a regression test. It reproduces the original failure under its triggering conditions, fails on the pre-fix code, passes with the fix, and asserts observable behavior rather than private implementation details. The test-first requirements in [references/testing.md](references/testing.md) decide whether it is written before or after the fix. When reproduction is intermittent or the required environment is unavailable, report that limit and what remains unverified instead of claiming a proven fix.

### Independent Review

The agent that produced a piece of work does not review it. When this conversation wrote or changed any part of what is under review, whether code, screens or a fix, the review is carried out by a reviewer in a separate context, dispatched through **agent-delegation**.

The exception is a small, low-risk change of its own: a few lines that are easy to revert, that change no shared contract, and that touch nothing the review skills treat as high-impact or security-relevant. When in doubt, it is not small. The main conversation does every review that applies to such a change itself, lightly, dispatches no one, and says in its report that it did.

- The main conversation decides which reviews apply and dispatches them. It gives each reviewer the request, the acceptance criteria, where the work is, and the review skill to follow. It does not pass along its own reasoning about the work or its opinion of it.
- When the reviewers return, the main conversation checks each finding against the code or the rendered result, then merges and reports them. It does not add a verdict of its own that the work is sound.
- Work this conversation had no part in producing, such as a diff the user hands over or someone else's PR, may be reviewed directly.

### Findings and Severity

**diff-review**, **security-scan**, **ui-review** and **acceptance-review** report with this format and scale, so their results merge into one list.

A finding is confirmed only when code or observed behavior shows a concrete failure scenario. Each confirmed finding names its evidence: `ran:` with the command and what it printed, `seen:` with the screen and state that was looked at, or `read:` with the lines that show it. Run the failure whenever that is possible within what the reviewer may do: an existing test or command, or a throwaway script kept in a temporary directory outside the project. A finding that could have been run that way and was only read is reported as needing investigation. When it cannot be run, `read:` confirms it only if the lines leave no doubt. A concern backed by evidence but missing a decisive fact is reported as needing investigation, with the missing fact and how to verify it. Speculation and style preferences are not findings.

| Level | Meaning |
|---|---|
| P0 | Must be fixed before merging or release: a security breach, data loss, an outage, or a main flow that cannot be completed |
| P1 | Serious: incorrect behavior, a major regression, or exposure of other users' data is likely. Normally fixed before merging |
| P2 | Moderate and localized. Actionable; may be scheduled after merging when the risk is accepted |
| P3 | Minor: small impact, or it needs several unlikely conditions together |

Each review skill adds the criteria for assigning these levels in its own domain.

```text
[P0-P3] [CONFIRMED] location - trigger, impact, description, recommended action - ran: | seen: | read: evidence
[NEEDS INVESTIGATION] location - observed evidence, possible failure, missing fact, verification step
```

`location` is a file and line, or a screen and state for rendered UI. An item that needs investigation describes its impact conditionally and carries no level. List confirmed findings from P0 to P3, then the items needing investigation.

### Staging and Commits

- Stage with explicit paths. `git add -A`, `git add .`, `git add --all`, `git commit -a` and `git commit -am` are not used, including in a fresh repository. The one exception is `git add --renormalize .` when a `.gitattributes` is introduced, which rewrites only files that are already tracked. Leave out build output, caches, operating-system metadata files and binaries the task did not ask for. List what is left out of the commit and why; do not silently stash, discard or include unrelated changes.
- Follow the user's or the project's commit arrangement. Without one, commit the fix on its own first, then its regression test in a separate commit. When a test is written and when it is committed are separate decisions.
- Before writing a commit message, read [references/commit-messages.md](references/commit-messages.md).

### Secrets

Never print the value of a secret, token, password, key or sensitive setting: not in replies, reports, commands, command output that can be avoided, delegation prompts, logs or commits. Refer to it by key name and location.

### Turn-End Report

End every turn of any ongoing task with a progress bar tied to the original goal: completed/total agreed items, current work, and what remains before completion. Use the existing plan or checklist and identify primary flows that are still unimplemented or unverified. Count only verified work that meets the agreed acceptance and delivery conditions; show pending acceptance separately.

Keep the scope and denominator stable unless the user changes them. If the total is unknown, show milestones without inventing a percentage or finish date. Item completion is not a time estimate; 100% requires the original goal and all delivery conditions to be met.

Every time the main conversation stops, also state on its own line what is still running or being waited on, whether or not a task is ongoing:

- Each background subagent, dispatched CLI, background command, watcher or scheduled wake-up: what it is doing, its identifier when it has one, and what will bring the conversation back (a completion notice, a timer, or the user).
- When nothing is running and nothing is being waited on, say so in plain words, for example「背景：沒有在跑的工作，也沒有在等的指令」.
- When the turn stops because it needs the user, say that the work is paused until they answer.

Check the actual state before writing this line; do not infer it from what was started earlier.

## What to Read When

| When | Read |
|---|---|
| Starting any task | [references/playbooks.md](references/playbooks.md) |
| Designing anything larger than a single-location change | [references/design.md](references/design.md) |
| Scripting a change; recording a follow-up; a new repository or `.gitattributes`; writing documents, rules, prompts or skills; touching `AGENTS.md` or `CLAUDE.md` | [references/changing-code.md](references/changing-code.md) |
| Choosing test timing, refactoring, editing skills or prompts | [references/testing.md](references/testing.md) |
| A second attempt at something that failed; a series of experiments; handing work off, pausing it or resuming it | [references/iterations.md](references/iterations.md) |
| Writing a commit message | [references/commit-messages.md](references/commit-messages.md) |
| Designing or changing a CLI, an MCP tool or an API | [references/tool-discoverability.md](references/tool-discoverability.md) |
| Creating or modifying Docker Compose files | [references/docker-compose.md](references/docker-compose.md) |

## Pre-Ship Checklist

- [ ] Every step of the playbook is done or marked `skip` with a reason.
- [ ] Scope and simplicity reviewed against Principles 2–3.
- [ ] The feature or problem is handled completely: root cause, same-pattern occurrences, and edge cases.
- [ ] Verification completed under Principle 4, including the end-to-end acceptance flows.
- [ ] Results demonstrate the agreed success criteria; any remaining gaps are reported.
