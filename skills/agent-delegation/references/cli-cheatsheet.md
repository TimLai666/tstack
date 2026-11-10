# CLI help entry points

For ordinary new dispatch, first run `python3 <skill-dir>/scripts/dispatch.py` for the overview, then read the `--help` of the subcommands you need. Tool order, number of levels, model limits and reasoning effort come from [policy.json](../scripts/policy.json).

On Windows, use `py -3 <skill-dir>/scripts/dispatch.py`; it requires Python 3.9+ and Windows 10+. Platform limits, the state directory and the CLI wrapper format are in the script's `--help` and `dispatch --help`.

| Tool | Native help entry points |
| --- | --- |
| OpenCode | `opencode --help`, `opencode run --help`, `opencode models` |
| Antigravity (agy) | `agy --help`, `agy models` |
| GitHub Copilot CLI | `copilot --help`, `copilot help permissions` |
| Codex | `codex --help`, `codex exec --help`, `codex debug models` |
| Claude Code | `claude --help` |

After a CLI update, check its actual interface. When a flag is not supported, keep the error and let the script take over; do not switch to an unapproved model or execution mode.

## Handing over to a built-in tool

Model choice, dispatch and reporting for `native_required` follow [script-execution.md](script-execution.md).

## Resuming a session

Reuse conditions and isolation requirements are in [dispatch-flow.md](dispatch-flow.md#agent-and-session-reuse). A built-in tool uses its resume feature for the existing agent; an external CLI uses the resume feature of the original session. Look up the parameters in the native help listed in the table above or in the built-in tool's documentation, and specify the ID explicitly; do not guess the session with "most recent".

When the script does not yet provide session resume, the main agent uses the native resume interface and keeps the task, ID, actual model, output and verification records. SKILL.md's ban on the host's own CLI, auto-approval, scope of files that may be changed, concurrency limits and acceptance review apply in the same way. Before and after resuming, the main agent checks the processes and file changes, including ignored files and the authorized sandbox.

The script's dispatch ID is for continuing dispatch state; it is not the model session ID. Do not claim a session was reused because dispatch state was restored.

## State and partial work

The script's state keeps the original task, attempt records, errors and output locations. Before continuing, the main agent reads the records, checks processes and disk differences, and adds the verified lessons. When resuming fails, handle it following [Tool failures](dispatch-flow.md#tool-failures); do not keep retrying a dead session. The main agent decides how partial results are kept and continued; the script does not delete, stash or reset them automatically.
