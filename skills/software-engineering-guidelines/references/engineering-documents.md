# Engineering documents

The layout, the index file and the writing rules for the documents described in the core's [Engineering Documents](../SKILL.md#engineering-documents).

## Layout

```text
engineering/
├── README.md            index of this directory
├── status.md            current progress, blockers, next ticket
├── architecture.md      technical decisions that hold across tickets
├── specs/<feature>.md   what is to be built and how to tell it is done
├── tickets/NN-<slug>.md one verifiable slice of work each
├── reviews/ui.md        review record of the built screens
├── reviews/security.md  kept security report
└── tasks/<task>.md      record of a long-running task: results, failed approaches, next check
```

Create a file or subdirectory only when there is content for it. A project that has its own location for one kind of document keeps it there, and `README.md` names that location.

## Files that stay at the project root

| File | Reason |
|---|---|
| `AGENTS.md`, `CLAUDE.md` | Agent tools read them from the root |
| `README.md` | The entry for the project's users and newcomers |
| `.gitattributes` | Git reads it from the root |
| `DESIGN.md` | The visual baseline, read from the root by design tools. Not written by this stack |

Nothing else is written to the root.

## README.md

Write `engineering/README.md` when the directory is created, and update it whenever a kind of document is added, moved or removed. List only what exists.

```md
# Engineering documents

Working documents for the people and agents developing this project. Documentation for the project's users is in `docs/`.

| Document | What it holds | Read it when |
|---|---|---|
| [status.md](status.md) | Current progress, blockers and the next ticket | Arriving to pick up work |
| [architecture.md](architecture.md) | Technical decisions that hold across tickets | Before changing architecture, tests or migrations |
| [specs/](specs/) | One file per feature: scope items, exclusions, flows, decisions | Before working on that feature |
| [tickets/](tickets/) | One file per slice of work, numbered in dependency order | Picking the next piece of work |
| [reviews/](reviews/) | Review records of the screens and of security | Before changing what a review covers |

## How they fit together

- A specification lists scope items (`S1`, `S2`, ...). Each ticket names the scope item it delivers.
- When a requirement changes, the specification changes first, then the tickets that name the changed item.
- A ticket is done when its work is merged and its acceptance criteria were checked. `status.md` then names the next ticket.
```

## Writing rules

- **Readable without any tool.** A person or an agent that has never used this stack can read and update every file. Describe a step by what is done, such as "reviewed before merging", and do not name a skill, a plugin or a command of this stack inside the documents.
- **Plain Markdown.** No file needs a script to be read or updated.
- **State files.** One file per subject, updated in place, with no date or branch in its name. Git holds the history.
- **Register in `AGENTS.md`.** `AGENTS.md` names `engineering/` and says when each document is read, so that any agent tool finds them.
