# Engineering documents

The layout, the index file and the writing rules for the documents described in the core's [Engineering Documents](../SKILL.md#engineering-documents).

## What each document answers

| Question during development | Document | How it changes |
|---|---|---|
| What should this feature do? | `specs/<feature>.md` | Describes the present; updated in place |
| How is the system built? | `architecture.md` | Describes the present; updated in place |
| Why was it built this way? | `decisions/NNNN-<topic>.md` | Added to, never rewritten |
| What is left to do, and how far along is it? | `tickets/` | Written, worked, then moved to `done/` |
| How does one work in this project? | `AGENTS.md` at the project root | Updated in place |

One question has one document. Before adding a file, name the question it answers and who reads it at which step; when an existing document answers that question, write there.

## Layout

```text
engineering/
├── README.md                  index of this directory
├── architecture.md            the system as it is now
├── specs/<feature>.md         what each feature does and how to tell it is done
├── decisions/NNNN-<topic>.md  one hard-to-reverse choice each, with the options rejected
├── tickets/NN-<slug>.md       open tickets
├── tickets/doing/             tickets in progress
├── tickets/done/              finished tickets
└── reports/                   only what the user asked to keep
```

Create a file or subdirectory only when there is content for it. A project that has its own location for one kind of document keeps it there, and `README.md` names that location.

There is no status file: a ticket's directory is its state. There is no review record: a review is delivered where it was asked for, and what it leaves undone becomes tickets.

A report the user asks to keep is a record of one moment. Name it `reports/<YYYY-MM-DD>-<kind>.md` and do not update it later.

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
| [architecture.md](architecture.md) | How the system is built: components, data flow, where tests hook in | Before changing the structure, the tests or a migration |
| [specs/](specs/) | One file per feature: what it does, what it leaves out, how to tell it is done | Before working on that feature |
| [decisions/](decisions/) | One file per hard-to-reverse choice, with the options that were rejected | Before proposing to change such a choice |
| [tickets/](tickets/) | One file per slice of work | Picking the next piece of work |

## How to work with them

- **Progress is where the ticket files are.** Open tickets are in `tickets/`, tickets in progress in `tickets/doing/`, finished ones in `tickets/done/`. A ticket can start when every ticket it lists under "Blocked by" is in `done/`. The number is a name, not an order.
- **A ticket is finished by the change that delivers it.** The same change moves the ticket file to `done/`.
- **A specification lists scope items** (`S1`, `S2`, ...), and each ticket names the scope item it delivers.
- **When a requirement changes, the specification changes first**, then the tickets that name the changed item, then the code.
- **A problem found and not fixed now becomes a ticket.**
- **A decision record is not edited after it is accepted.** A later decision gets a new record and marks the old one as superseded.
```

## Writing rules

- **Readable without any tool.** A person or an agent that has never used this stack can read and update every file. Describe a step by what is done, such as "reviewed before merging", and do not name a skill, a plugin or a command of this stack inside the documents.
- **Plain Markdown.** No file needs a script to be read or updated.
- **No dates or branches in the names** of specifications, the architecture record and tickets. Git holds the history.
- **Refer by name, not by path.** Tickets move between directories; refer to a ticket by its number and to a scope item by its id, without a link.
- **Link from the repository root.** A link from an engineering document to a file in the repository starts with `/`, such as `/src/server/auth.ts`, so that it still resolves after the document moves.
- **Register in `AGENTS.md`.** `AGENTS.md` names `engineering/` and says when each document is read, so that any agent tool finds them.
