# Dispatch pitfall checklist

Before every report, check each row; send back or correct any dispatch that does not comply.

| Pitfall | How to check |
| --- | --- |
| Dispatching without identifying the host, so the host calls itself | The first line of the report MUST contain "宿主：", the tool list contains no command of the host's own CLI, and the host's own entry uses the built-in subagent tool |
| A dispatched agent also loads this skill and dispatches further | A dispatched worker's report MUST NOT contain any dispatch action. If it does, send it back and check whether the first line of the prompt carries the worker marker |
| Dispatching implementation without a skeleton | Before dispatching implementation, the skeleton, the slot's expected results and the reviewed tests all exist |
| Skipping OpenCode for a hard slot without an opencode failure record | When OpenCode is skipped, the report names the slot of the same type in this task where opencode delivered an incomplete result or one that failed verification, and attaches that run's output |
| Changing model or skipping a level in order to reuse an existing agent | Both new and reused sessions MUST match this task's current level. A fallback attaches the actual failure evidence from this task that the rules require; quota exhaustion from other tasks or an existing agent's model does not substitute for it |
| Tests pass on the empty slots | When reviewing tests, run them once on the empty slots; the report attaches output in which all of them fail |
| The implementation agent changes the tests to pass | At acceptance, the files listed by `git diff` do not include test files |
| Two agents change the same file at the same time | Before dispatching the second, rerun `git status --short`; if paths overlap, wait for the first to finish |
| Adopting work after reading only the subagent's summary | The report MUST contain verification output that the main agent ran itself |
| Switching to a kind outside the decision table when a model does not exist | The reported model MUST belong to the kind in that decision table row and match what was recorded before dispatch |
| Codex uses the wrong model | The model for review, acceptance review, deep research and decision is GPT-6 or later with sol in its name. luna is used only for the decision table rows for writing tests / implementation / fixing bugs, fast read-only exploration, chores and classification; frontend design is not dispatched to luna |
| effort not at the default or above the limit | Dispatches that have an effort flag use `medium`; when raised, the report states the reason. No dispatch uses `max`. Opus taking over a coding slot uses `low`. agy's Claude and the host's built-in subagent tool have no such flag and are not checked |
| More than three runs of the same CLI at once | Before dispatching, list that CLI's running dispatches; including this one, there are no more than three |
| Opus not dispatched according to the decision table | When the reported model name contains opus, that dispatch MUST belong to a task for which the decision table lists Opus, and follow the handover order. When taking over a coding slot, attach the output of Sonnet failing verification twice in a row on the same slot; when dispatched with `claude -p`, the flags include `--effort low` |
| Classification task not using the decision table's model choice | Copilot uses Auto; for other tools the model name MUST contain haiku or luna and MUST NOT contain opus or sonnet |
| Task dispatched to a Sonnet or Haiku below 5.5 | When the reported model name contains sonnet or haiku, the version MUST be 5.5 or later |
