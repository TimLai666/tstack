# Commit messages

Follow the user's explicit instructions first, then the project's documented
commit-message rules. Before drafting a commit, read the relevant project
instructions (such as `AGENTS.md` and `CONTRIBUTING.md`) and any saved preference
through **project-memory**. Commit history alone does not establish a documented
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
question. A one-commit exception applies only to that commit and must not be
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
