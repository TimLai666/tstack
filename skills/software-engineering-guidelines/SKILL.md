---
name: software-engineering-guidelines
description: "Software engineering guidelines for any software change. This skill MUST be loaded before requirement clarification, architecture/design, implementation, refactoring, code review, testing, shipping, or creating Git commits (including standalone commit requests), and MUST NOT be skipped because the change is a one-liner. Covers simplicity, complete delivery based on a coherent implementation design, testing-first for high-impact changes with TDD (Test-Driven Development), and verifiable success criteria. Triggers on: 任何軟體規劃, 需求釐清, 架構設計, 寫 code, 改 code, 做功能, 修 bug, refactor, 開發, coding, development, 實作, 實現, 寫程式, 改程式, 加功能, 修問題, code review, 測試, 重構, init, 初始化專案, 建立 CLAUDE.md, 建立 AGENTS.md"
metadata:
  version: "1.14.0"
---

## Core Principles

### 1. Think Before Coding

**Verify what you can. Make material assumptions and tradeoffs clear.**

Before implementing:

- Own the implementation design. Resolve routine technical details from the code, documentation, existing conventions, and focused checks. Use reasonable assumptions within the authorized scope, explaining them when they help the user assess the result. Do not turn internal design work into an exhaustive questionnaire or require approval for each implementation detail.
- Ask the user only when a gap remains after checking available information and would materially affect the result, scope, authorization, or an important tradeoff. Explain the relevant difference and recommend an approach. Continue independent work while that decision is pending.
- If a simpler approach exists, say so. Push back when warranted.
- Work out a coherent design for the full authorized outcome before filling individual components. Trace required flows through responsibilities, interfaces, data lifecycle, dependencies, failure and recovery behavior, and acceptance checks. Consider relevant boundary cases, duplicate or concurrent operations, interruption, compatibility, and downstream effects before coding. Scale the depth to the task and resolve foreseeable gaps before they become implementation rework.
- Compare materially different approaches against correctness, compatibility, maintainability, and actual resource constraints. Choose the simplest approach that satisfies the full agreed requirements. Validate uncertain assumptions that could invalidate it with focused checks, then proceed once material decisions have sufficient support. Apply the design and required quality from the first implementation. Revisit settled decisions when new evidence or changed requirements warrants it.

### 2. Simplicity First

**Simple, correct implementations for the full agreed requirements. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- When the goal can be met either by removing code or by adding code, remove code. The removal stays within the task's scope and keeps every other behavior intact.
- Use concise, maintainable implementations. Do not rewrite accepted code solely to reduce line count while required outcomes remain incomplete.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Complete, Surgical Changes

**Touch everything the task needs and nothing else. Clean up only your own mess.**

Plan each turn to finish the full authorized outcome, including implementation, integration, verification, and necessary repairs. Do not reserve required work for a later turn or wait for another prompt to finish it. Intermediate milestones organize the work within the turn; they are not delivery boundaries unless the user explicitly requested staged delivery. If a real blocker prevents completion, finish independent work and report the exact remaining gap and what is needed to resolve it.

Judge completion over the whole agreed feature or problem. Order intermediate work by Principle 5's whole-goal priorities:

- A feature covers every layer, entry point, and edge case it needs.
- A fix covers the root cause, every occurrence of the same pattern, and the related edge cases. Do not stop at the reported spot.

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting; don't refactor things that aren't broken; don't delete pre-existing dead code. Mention what you spot and suggest how to handle it — see the recording rule below.
- Match existing style, even if you'd do it differently.
- Remove imports/variables/functions that YOUR changes made unused.
- Write and change files with the editing tools. Content that spans lines or contains non-ASCII characters, quotes or backslashes does not go through shell quoting or a heredoc.
- When a change has to be scripted, read the target first, confirm the number of matches the script will replace, write the result to a temporary file, and swap it in only after checking it. Before overwriting, restoring or discarding a file, read its full diff, including uncommitted work that is not yours.

**Recording rule:** Mention discovered out-of-scope issues to the user and record them using the project's existing follow-up location and conventions. If none are established, use `## Follow-ups` in the project's `AGENTS.md`, creating the section or file if needed. Preserve existing content and avoid duplicate records. When an issue is resolved, follow the project's completion convention; under the default `Follow-ups` arrangement, remove the resolved entry. See [references/follow-ups-example.md](references/follow-ups-example.md) for the default format and examples.

**Agent context files:** Inspect and follow the project's existing arrangement for agent instructions. When initializing project docs (e.g. `/init`) or asked to create or update agent context files, use this default if no arrangement exists: put the operating instructions in `AGENTS.md` and make `CLAUDE.md` a one-line pointer: "Read `AGENTS.md` before doing any project work." Create missing files as needed. Existing substantive instructions in either file count as an arrangement to preserve; a missing counterpart alone is not a reason to reorganize them.

**Git attributes:** Every Git repository has a root `.gitattributes`. When it is missing, create it while initializing the project or before the first commit of the current work. Start with `* text=auto eol=lf`, then add the entries the project's files need, such as `binary` for binary formats and `eol=crlf` for Windows scripts (`*.bat`, `*.cmd`). In a repository that already has commits, run `git add --renormalize .` after adding the file and commit the file with the resulting normalization as a separate commit. Preserve existing entries.

**Content boundary at every level:** An `AGENTS.md` at any directory level contains only what an agent must follow or check on every turn of work in that scope: operating rules and agent-facing reminders such as `## Follow-ups`. Project or module introductions, background, structure overviews, and usage notes go in the `README.md` at the same level. Move misplaced content to the correct file when editing either one.

**Writing documents, rules, prompts, and skills:** Before editing existing content, load `human-writing` and apply [principle 8A](https://github.com/TimLai666/skills/blob/main/plugins/writing-and-design/skills/human-writing/references/human-writing-principles.md#8a-write-the-current-document-for-its-current-reader) for placement, consolidation, and consistency checks. If that skill is unavailable, read the linked rule before editing. When writing rules, prompts, or skills, state the rule itself. Do not explain the reason behind it, and do not write it as a change record (for example, a date and what it was changed from). Update the rule text in place.

The test: Every changed line should trace directly to the user's request.

### 4. Testing Strategy (Test-First + scoped TDD)

**Choose verification that demonstrates the change works and matches its impact.**

Baseline rule:

- Every behavior-changing change needs test coverage.
- For text, formatting, or documentation changes, use checks suited to the affected content.
- Run the full test suite according to the project's rules.
- Before a check writes to an external system, confirm that a test environment exists and how the written data will be removed. With neither, do not write to it for verification; ask the user how to verify.
- Run the project's linter and type checker when provided, and report their results alongside the tests. Unresolved failures mean verification is incomplete.
- For small, local, low-risk fixes, add/update tests around the change (before or immediately after implementation is acceptable if justified).
- For large changes, broad-scope changes, or major new features, you MUST apply TDD: write the failing test first, then implement — don't write code and backfill tests.

判斷大改動的指標（任一符合即可）：

1. 觸及多個模組或層級（例如 UI、API、資料層同時調整）。
2. 變更公開行為邊界，如 API 契約、資料模型、存取規則、核心流程。
3. 新增核心新功能，或重構高風險路徑（付款、認證、權限、資料遷移、狀態轉換）。

Rules:

- **Bug fixes need a test that reproduces the bug; use the test-first requirements above to determine timing.**
- **Before refactoring, establish the result of relevant tests; rerun them after the change.**
- **Don't weaken a test just to make it pass.** Unless the test itself is wrong.
- **For behavior-changing edits to skills, prompts, or agent workflows, compare the current and candidate versions on the same tasks in fresh contexts with the same model, tools, data access, and resource limits.** Scale the comparison to the change. Inspect actual decisions, artifacts, acceptance results, unsupported retries, premature stops, and cost. Keep acceptance cases separate from cases used to revise the instructions. Retain the current version as an eligible outcome; inconclusive comparisons do not establish improvement.

### 5. Goal-Driven Execution

**Define success criteria. Use observed progress to choose each next step.**

Transform tasks into verifiable goals — e.g. "Add validation" → "Write tests for invalid inputs, then make them pass".

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Derive concrete success criteria from the request and available project evidence. Resolve routine gaps yourself and apply Principle 1's clarification threshold to material unknowns.

**Skeleton first.** Before filling in logic for a new project, feature, or fix, write a skeleton that fixes the scope:

- New project or feature: code that runs end to end, with entry points, data shapes, and empty slots. Give each slot its signature (inputs, outputs, how errors are reported) and a list of expected results, including edge cases. Add two or three end-to-end acceptance flows that exercise the whole path.
- Fix: the root cause, the full list of places to change, and the check that proves each one.
- Include pseudocode only when it is already worked out.
- Place independent slots in separate files.
- Scale the skeleton to the task. A single-location change needs only its expected results and check.

Fill the slots in the order below until their checks and the acceptance flows pass. When work is handed to other agents, follow **agent-delegation** when it is installed. Otherwise give each agent its slot's signature, expected results, and checks. The agent that fills a slot does not edit its checks. Review the returned work yourself before accepting it.

#### Whole-Goal Priority

- For multi-part work, identify the required outcomes, their dependencies, and which primary flows remain unimplemented or unverified. Choose the next work from these gaps before deepening an already working part.
- Implement production-intended components according to the agreed design, with the correctness and interfaces their role requires. Integrate and verify a complete primary flow early, then cover the remaining primary flows before optional local refinement. Do not substitute a knowingly inadequate design or disposable implementation for required work. Scaffolding, disconnected components, and mock outputs do not establish working coverage. Keep intermediate gaps explicit; complete all required edge cases and checks before delivery.
- Once a part meets the criteria needed for the current integrated flow, move to the next uncovered outcome or blocking dependency. Defer extra abstraction, optimization beyond the agreed target, cosmetic polish, and repeated passing checks unless new evidence justifies them. Complete necessary local work first when correctness, safety, data integrity, or a downstream dependency prevents valid integration.
- Follow an explicit user priority or narrowly scoped request. Do not expand the task to create breadth. Before returning to a covered part, identify the unmet requirement or new evidence that makes that work more valuable than the remaining gaps.

#### Evidence-Guided Iterations

Apply these checks around a meaningful experiment, implementation attempt, or revision within the ongoing work. Use them to verify and repair the complete implementation during the current turn, not to defer foreseeable requirements or delivery to another turn. Scale the record to the task; routine actions within an attempt do not each need a separate plan or report.

1. Before an attempt, identify the acceptance gap or decision-relevant uncertainty it addresses and the observable result expected. For uncertain claims, state what would support, weaken, or leave them unresolved, including relevant alternative explanations. Prefer a feasible check that distinguishes alternatives at low cost; reuse applicable evidence.
2. After the check, compare the result with the attempt's starting state and the best supported result under the same criteria. Identify verified improvement, a necessary repair or prerequisite, an informative negative result, repetition, regression, or insufficient evidence. Tie each claimed gain to evidence and the original goal. A prerequisite counts only toward the acceptance condition it enables; execution or compilation alone does not establish correctness or validate a research claim.
3. Apply whole-goal priorities, then choose the next action by its expected contribution to the original goal, evidential value, and remaining cost. Preserve supported gains, repair an identified defect, or investigate alternatives that predict different outcomes. Revise or abandon a contradicted approach. For inconclusive results, improve the measurement or obtain missing evidence before drawing a conclusion. A negative result counts as progress only when a valid check rules out a relevant possibility or changes a justified decision.
4. Before retrying, identify new evidence, a changed condition, or a distinct diagnostic check and what it can establish. When none is available, stop repeating that attempt and continue independent work that can advance the goal. Request help only for a material evidence, access, expertise, or authorization gap. Do not stop solely because an arbitrary number of attempts failed, or change acceptance criteria to make an attempt pass.
5. Preserve the best supported candidate and enough evidence to compare later revisions. Before continuing, handing off, or resuming, update and read the existing task record for confirmed results, failed approaches and their conditions, evidence locations, unresolved questions, and the next discriminating check. Link revisions to the candidate they changed; do not count repeated versions as separate gains. Use the existing coordination file, or `docs/software-engineering-guidelines/` when a persistent record is needed, and preserve unrelated content.

### Progress and Background Status at Every Turn End

End every turn of any ongoing task with a progress bar tied to the original goal: completed/total agreed items, current work, and what remains before completion. Use the existing plan or checklist and identify primary flows that are still unimplemented or unverified. Count only verified work that meets the agreed acceptance and delivery conditions; show pending acceptance separately.

Keep the scope and denominator stable unless the user changes them. If the total is unknown, show milestones without inventing a percentage or finish date. Item completion is not a time estimate; 100% requires the original goal and all delivery conditions to be met.

Every time the main conversation stops, also state on its own line what is still running or being waited on, whether or not a task is ongoing:

- Each background subagent, dispatched CLI, background command, watcher or scheduled wake-up: what it is doing, its identifier when it has one, and what will bring the conversation back (a completion notice, a timer, or the user).
- When nothing is running and nothing is being waited on, say so in plain words, for example「背景：沒有在跑的工作，也沒有在等的指令」.
- When the turn stops because it needs the user, say that the work is paused until they answer.

Check the actual state before writing this line; do not infer it from what was started earlier.

---

### 6. Tool and API Discoverability

When designing or changing our CLI tools, MCP tools, or APIs, put their supported operations and usage in the interface itself.

- **CLI:** Provide an overview listing all supported commands. A bare invocation should show the overview when it has no existing operation to perform. Always implement `--help`, with parameters, required values, defaults, examples, and errors documented in each command's help. A single-operation script can use its top-level help for both overview and details.
- **API:** Provide an overview endpoint listing all supported public endpoints and their methods, with links to each operation's usage. Use the API base path when available; preserve an existing base operation by linking to a dedicated overview instead. Publish OpenAPI JSON covering parameters, request and response schemas, authentication, and errors. Each operation's documentation must be discoverable from the overview.
- **MCP:** Document each operation in its registered tool description and input schema, including usage constraints and return behavior. Tool registration supplies discovery, so a separate overview tool is not required.
- **Skills:** Explain tool selection, workflow, and decision-relevant constraints. Point to the tool's overview, help, registered schema, or OpenAPI document instead of duplicating its complete command and parameter manual in a skill or its references.
- **Updates:** Change the overview, command help, operation descriptions, and OpenAPI JSON together with the affected functionality. Prefer generating them from the implementation's command or route definitions. Verify that every supported operation is discoverable and that documented examples, parameters, and responses match actual behavior before delivery.

### 7. Docker Compose Environment Variables

When creating or modifying Docker Compose files:

- MUST use braced variable interpolation (`${VAR}`) for externally supplied values. Declare container environment variables explicitly under `environment`, for example `LOG_LEVEL: ${LOG_LEVEL}`. MUST NOT use the service-level `env_file` attribute.
- MUST use `${VAR:?必須設定 VAR}` for every required variable, for example `DATABASE_URL: ${DATABASE_URL:?必須設定 DATABASE_URL}`. Required variables must reject both unset and empty values. MUST NOT supply fallback defaults for required variables.
- Supply interpolation values through the shell environment, Compose's default `.env`, or the CLI `--env-file` option. These are interpolation sources, distinct from the prohibited service-level `env_file` attribute. Keep actual secrets out of version control and list required variable names in `.env.example` without real credentials.
- Before delivery, validate with `docker compose config --quiet` using the same files and interpolation sources as the startup command. Verify that valid values pass and each required variable fails when unset or empty. Do not print or retain resolved configuration containing secrets.

## Workflow

### A. Before Writing Code

1. Establish the requirement and approach (Principle 1).
2. Define success criteria (Principle 5).
3. Select verification and establish required pre-change results (Principle 4).
4. Write the skeleton (Principle 5).

### B. While Writing Code

Fill the skeleton using Principles 2–4 and Principle 5's whole-goal priorities. Before and after each meaningful attempt, apply the iteration checks and use the result to choose the next action.

### C. After Completion

1. Complete and report verification (Principle 4).
2. Review the Pre-Ship Checklist.
3. Before ending the turn, compare the result with the full authorized outcome. Continue any required work that can still be completed, then report progress against the original goal using Principle 5.

---

## Commit Messages

Follow the user's explicit instructions first, then the project's documented
commit-message rules. Before drafting a commit, read the relevant project
instructions (such as `AGENTS.md` and `CONTRIBUTING.md`) and any saved preference
through **project-memory** when it is installed. Commit history alone does not establish a documented
rule. Reuse an already confirmed choice without asking again.

If no documented rule or confirmed choice exists, inspect recent commit
messages. When they follow the default below, or the project has no commits,
use the default without asking. Ask only when the inspected history contains a
different style: show the observed difference and ask whether to adopt the
default or retain a custom project style. Wait for that decision before creating
the commit. If the user declines the default without specifying an alternative,
ask which format they want. Do not record automatic fallback as a user decision.

After confirmation, record a custom project style in the project's `AGENTS.md`,
including its format and any specified language, preserving unrelated content.
If the style is already documented elsewhere, link to that source instead of
duplicating it. If the user adopts this skill's default, use it and record that
choice through **project-memory** as preference `commit-message-style`, with
source `software-engineering-guidelines`, so later commits do not repeat the
question. Without **project-memory**, record the adopted default in the project's
`AGENTS.md` the same way as a custom style. A one-commit exception applies only to that commit and must not be
saved as the project's ongoing style. Report any failure to save a decision.

The default format is Conventional Commits:

```text
<type>(<optional-scope>): <summary>
```

Use an appropriate type such as `feat`, `fix`, `docs`, `refactor`, `test`, `build`,
`ci`, `perf`, `style`, `chore`, or `revert`. Omit the scope when it adds no useful
context. Write a concise, imperative summary of the actual change; add a body
when the reason or consequences need explanation. Mark breaking changes with
`!` or a `BREAKING CHANGE:` footer when applicable.

Default to English for the subject and body unless the user or project specifies
another language. Resolve format and language independently: a project-specific
format does not change the default language unless it also specifies one.

Examples:

```text
fix(auth): handle expired sessions
docs: clarify installation steps
```

## Pre-Ship Checklist

- [ ] Scope and simplicity reviewed against Principles 2–3.
- [ ] The feature or problem is handled completely: root cause, same-pattern occurrences, and edge cases.
- [ ] Verification completed under Principle 4, including the end-to-end acceptance flows.
- [ ] Results demonstrate the agreed success criteria; any remaining gaps are reported.
