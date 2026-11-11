# Ticket lifecycle

How a ticket moves from written to done, how it is split, and how it is mirrored to an issue tracker. These apply to whoever works a ticket, in any project that keeps tickets as files. The ticket format is in [Ticket breakdown guidelines](ticket-breakdown-guidelines.md).

## The board

A ticket's state is the directory it is in. Nothing else records it.

```text
engineering/tickets/
├── 05-a-customer-can-cancel-a-booking.md    open
├── 06-a-shop-can-set-closed-days.md         open
├── doing/04-a-customer-can-reschedule.md    in progress
└── done/01-project-scaffold.md              done
```

- The number is the ticket's name. It does not set the order of work.
- A ticket can start when every ticket it names under `Blocked by` is in `done/`. Any ticket that can start may be picked, and several may be in progress at once.
- Tickets refer to each other, and specifications refer to tickets, by number and never by a link or a path. A link from a ticket to any other file in the repository starts from the repository root, with a leading `/`.
- No index repeats a ticket's state. A list of tickets kept beside them names each ticket and nothing about its progress.
- A ticket that cannot proceed stays where it is and gets a `**Blocked:**` line that says what is missing and who or what it waits for. Remove the line when it clears.

There is no status file. To report progress, list the three directories.

## Pick up

1. List `engineering/tickets/`. Take the ticket the user names, or one that can start.
2. Read the ticket, the tickets that block it, the specification scope item it names, and `engineering/architecture.md`.
3. Check whether it has to be split: see [Splitting a ticket](#splitting-a-ticket).
4. Move it to `doing/`. In a project that mirrors tickets to issues, mark the issue as in progress instead: see [Mirroring to an issue tracker](#mirroring-to-an-issue-tracker).

## While working

- **A requirement or specified behavior changes**, including through a bug fix: follow "Keeping it in sync" in [Specification guidelines](spec-guidelines.md) before changing the code.
- **A hard-to-reverse choice is made**: record it as [Decision records](decision-records.md) sets.
- **Something is found and left for later**, such as a review finding that is not fixed now or a problem outside this ticket: write a fix ticket for it. Do not leave it only in the conversation.
- **The work spans sessions**: keep what the next session needs under `## Notes` in the ticket: confirmed results, approaches that failed and why, and the next check to run.

## Close

Close a ticket when its work is merged, or handed back when the project has no merge step, and every acceptance criterion was checked. A ticket whose checks are not finished stays in progress.

- Move the ticket to `done/` in the same change that delivers the work, so that the board and the code change together.
- Remove its `## Notes` once nothing in them is needed again; move what stays true to the specification, the architecture record or a decision record.
- A parent ticket closes when all of its child tickets are in `done/`.

## Splitting a ticket

Check at pick-up. Split the ticket before writing code when either holds:

- Its acceptance criteria are stated through a reference: "the same as product X", "every feature of Y", "move module Z over".
- It cannot be finished and verified in one session and one pull request.

Steps:

1. **Take the inventory from the real thing.** Open the reference itself, such as the running product, its menus, its API, its source or the old module, and list every function it has, each with where it was seen. Do not list from memory.
2. **Decide each item.** Mark each one as in scope, not doing, or deferred, and get the user's confirmation of the list.
3. **Update the specification first.** Put the confirmed list under the scope item this ticket names, and the excluded items under `Not doing`.
4. **Write one child ticket per in-scope item**, each a vertical slice of its own, naming the parent. Number them after the parent: `07.1`, `07.2`.
5. **Turn the parent into the index.** Its body becomes the inventory with the child ticket of each item. It delivers nothing itself.

A child ticket that is still too large is split the same way.

## Mirroring to an issue tracker

Mirroring is optional. Do it when the project already mirrors its tickets, or when the user asks for issues to follow the work. The ticket file stays the ticket.

| | Source | The other side |
|---|---|---|
| Content: deliverable, acceptance criteria, blockers, scope item | The ticket file | The issue body, generated from the file and overwritten when the file changes |
| Discussion | The issue's comments | A decision reached there is written into the ticket file, the specification or a decision record |
| Done | Both, changed by the same merge | — |

- The ticket file carries an `**Issue:**` line with the issue number. The issue title starts with the ticket number, and the issue body starts with the path of the ticket file and a line saying that the body is generated from that file.
- In progress is shown on the issue, by assignment or a linked pull request, and the file stays out of `doing/`: a move made on a branch is not visible to others until it is merged.
- The pull request that delivers the ticket moves the file to `done/` and closes the issue through its description.
- A child ticket is mirrored as a sub-issue of its parent's issue.
- When the issue tracker cannot be reached, change the ticket file and report which issues were not updated. Do not report them as synchronized.

## Handing over

Before another agent or a later session takes over, the repository alone has to be enough:

- [ ] Every ticket is in the directory that matches its real state.
- [ ] Each ticket in progress has current `## Notes`, and each blocked ticket has its `**Blocked:**` line.
- [ ] Decisions made since the last handover are in the specification or a decision record, not only in the conversation.
- [ ] `AGENTS.md` is current, and `CLAUDE.md` points to it.
