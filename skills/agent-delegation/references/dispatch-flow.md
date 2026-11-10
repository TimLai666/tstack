# Dispatch flow details

Each step of the dispatch flow in [SKILL.md](../SKILL.md) points here. Read only the section for the current step.

## Before dispatching

For an empty-context readability review, its inputs and redispatch follow that section's isolation rules; all other checks apply as usual.

- [ ] The main agent loads the current project's memory following the `project-memory` skill and searches it for lessons that may apply to this subagent's task. Memory already loaded may be reused, but filter again when the task scope changes. Put the applicable conditions, key pitfalls, verified approaches and sources into the prompt; do not give only keys or ask the subagent to look them up itself, and do not paste whole unrelated memories. When an old lesson does not match the current state, handle it with project-memory's obsolescence verification rules.

- [ ] Run `git status --short`. When there are uncommitted changes, check file by file whether they are your own from this turn or another agent's partial work. If they are partial work, deal with it before dispatching.
- [ ] Confirm that no other agent that writes files is currently running on this set of files. Only one agent that writes files may work on the same set of files at a time.
- [ ] Confirm the CLI you will use has fewer than three runs; if it is full, wait for one to end.
- [ ] Before parallel dispatch, give each run its own files that may be changed and its own output directory, not overlapping each other and not overlapping any directory the main agent itself will clean or overwrite.
- [ ] Parallel dispatches that need a browser each use their own browser instance, not a shared one.
- [ ] In an unattended scheduled or background flow, first set the number of parallel runs and each dispatch's time or tool-call limit, and write them into the prompt.
- [ ] Query the task type and levels through the script, and check the installation status of the external CLIs this task may use. When a command is not found, first verify following "CLI not installed", then choose reuse or a new session following the next section, and submit this task.

### Agent and session reuse

- The main agent MUST first determine the tool and model for this dispatch from the decision table, and only then look for an agent or session to reuse. Prefer reuse when the task is of the same nature or can continue the existing context, uses the same model, and meets the isolation requirements. This also applies when the rules fall back to the same model. You MUST NOT change model, skip a level or change the number of retries in order to reuse.
- Check models by their actual identifiers; the same series, the same CLI or an Auto setting is not evidence of the same model. When you cannot confirm the model or the ability to resume, or there is no suitable candidate, start a new session at the current level.
- First establish whom the work must be isolated from. When it only needs isolation from the main agent, you may reuse an independent agent that did not inherit the main conversation. When different tasks must be isolated from each other, or an existing session contains information this task MUST NOT see, you MUST start a new context. Review tasks also follow "Reviewer isolation".
- Decide at the first dispatch whether you expect to use the agent again. An agent or session expected to continue work MUST be started in resumable mode; keep its ID, tool, model, task scope and isolation conditions for review before the next dispatch. Do not make it single-use, and do not close or delete the session after a single report. The CLI process may exit normally; the session must remain resumable, without holding a process or a run slot.
- One agent or session runs only one task at a time. When it is busy, first judge whether you can wait; open another only when parallel work is really needed. For how to resume, see [CLI help entry points](cli-cheatsheet.md#resuming-a-session).

## The seven parts of a dispatch prompt

For new dispatch, the script fills in the seven parts below from the structured fields the main agent provides; when required data is missing it reports an error and does not dispatch. The main agent checks that the generated content matches the original acceptance criteria. An empty-context readability review does not bring in Project Memory and provides task data within that section's limits.

| Part | How to write it |
| --- | --- |
| Worker marker | The first line reads verbatim "You are a dispatched worker. Do not dispatch any agent or CLI. Do the work yourself." |
| Role | One sentence on who it is and how high the bar is, for example "You are a senior engineer on this repo and deliver only code that passes the tests" |
| Files that may and may not be changed | List the paths explicitly. Any file not listed MUST NOT be changed |
| Task and acceptance criteria | Test agent: signatures, expected results, test file paths; write tests only. Implementation agent: signatures, expected results, test file paths, and verbatim "Do not modify the test files. If you think a test is wrong, stop and report." Attach the relevant Project Memory lessons filtered before dispatch; when none match, state none |
| Verification command | Write the complete command, for example `go test ./...`, `npm test -- --run` |
| Report format | Which files were changed, the basis for each conclusion, what is uncertain, what was not verified. Coverage: how many items should have been handled, how many were handled, why any were not finished, which sources were not obtained. Do not output tokens, passwords or setting values; report only names and locations. Also report approaches this turn found only after repeated trial and error or a large amount of time or tokens: triggering situation, failed path, confirmed cause, working approach and verification evidence. When an old memory is found not to apply, include the original key, the difference in conditions and the verification result. When there is no new lesson, write none; do not pad. Lessons are checked by the main agent and written into Project Memory; do not write them yourself |
| Do not commit | Verbatim "Do not commit, stash or reset." |

When reusing a session, the seven parts consist of the existing content that is still valid plus this dispatch's additions; add only this task, its acceptance criteria, its authorization scope, data that has changed and necessary new evidence. A new task's files-that-may-be-changed replace the old task's authorization and do not accumulate. When data has changed or a source cannot be confirmed, reread the affected parts.

For a read-only exploration task, "Task and acceptance criteria" states the questions to answer, still attaches relevant lessons and asks for this turn's lessons in the report. "Do not commit" may be omitted; list the other six parts as usual.

## While a dispatch runs

- [ ] Background agents and background commands notify the main agent when they end. Wait for the notification; do not schedule wake-ups or poll.
- [ ] When a background agent is interrupted, look at the disk first, with `git status --short` plus `git diff --stat`, to judge how far it got.
- [ ] When redispatching, retrieve the original prompt from the log file; do not rewrite it from memory. For Claude Code subagents it is at `head -1 ~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`; for other CLIs see the resume column of the cheat sheet.
- [ ] Before redispatching, add the previous worker's verified relevant lessons to the original prompt, keeping the evidence and uncertainties, then hand it to the next worker.
- [ ] Before redispatching, decide what to do with partial work: keep it and tell the new agent, or clear it with `git checkout -- <file>`.

## Tool failures

Authorization for ordinary dispatch includes retrying and redispatching under the script's rules. The main agent MUST handle tool failures itself and continue, and MUST NOT ask the user whether to retry, redispatch or continue because of a single tool failure, exhausted quota, unavailable model, missing login or unavailable built-in tool. Handover order and reuse conditions follow the decision table and "Agent and session reuse".

The script records the raw output and actual flags of every failure. For `native_required`, the main agent dispatches with the designated built-in tool and, on failure, continues with the actual error. `cli_failed` and `awaiting_review` are both decision points for the main agent, not confirmation points for the user: the main agent itself checks the process, the disk, partial work and verification results, then continues through the script with the original dispatch ID and the actual evidence, observing the limits on same-level retries and on not skipping levels. When you cannot confirm that the process has stopped or that partial work can be safely continued, remove the blocker first; do not redispatch blindly.

Stop and ask the user to decide only when every option for the type has failed, or when continuing really requires the user to log in, grant permissions, pay extra, widen the task scope or decide on handling that may lose work. When a single tool needs one of these but there is still an authorized option that can safely continue, first redispatch through the script; do not ask the user to fix that tool. The designated-model consultation for changes to an existing API keeps that section's failure handling.

### CLI not installed

- Before skipping a CLI because it is not installed, the main agent MUST verify the installation status, and MUST NOT conclude it is not installed from a single `command not found`, an empty `which` result or a script launch error alone. First check command resolution and PATH in both the current runtime and the shell the user normally uses, then confirm from existing settings, package manager install records and the tool's standard install locations. Check only the relevant locations; do not scan the whole disk.
- When you find a candidate executable, run a version or help query with its explicit path to confirm it is that CLI. Installed but not on PATH, insufficient permissions, a broken launcher or a missing runtime are each recorded as the matching launch problem, not as not installed. When verification is blocked, record it truthfully as unconfirmed and proceed on the error evidence you have; do not claim it is not installed.
- Once confirmed not installed, keep the verification commands and results, skip that external CLI following the decision table and continue with the available options. Do not install or reinstall it yourself, or use a launch method that downloads the tool automatically. Unless the user gives an explicit instruction to install, do not install a CLI to complete a dispatch. After confirming it is not installed, add `--not-installed` when continuing, and put the verification commands and results in `--failure-reason`. The script records this verification; later dispatches skip that tool automatically while PATH has not changed, the command is still not found and fewer than 7 days have passed, and attach the evidence from that time in `attempts`. If any of these three conditions does not hold, it launches as usual and verifies again. Do not add this flag when you cannot confirm whether it is installed. Judge the availability of the host's built-in tool separately; do not skip it because an external CLI of the same name is not installed.

| Symptom | What to report |
| --- | --- |
| CLI not installed or failed to launch | Paste the verification commands, results and conclusion, distinguishing not installed, PATH problems and other launch errors |
| Model does not exist or the CLI needs an upgrade | Paste the original error and the output of `agy models` / `opencode models` / `codex debug models` |
| Permission denied, not logged in | Paste the original error and state which permission or login command is needed |
| Timeout | Paste the timeout setting and the part already completed |
| Quota exhausted (rate limit, quota, usage limit) | Paste the original error |
