---
name: prevent-recurrence
description: "Turn a mistake that keeps happening into something that cannot happen or that fails loudly, instead of adding another written rule. This skill MUST be used when the same kind of mistake has happened a second time in a project, when the user says an agent keeps doing something wrong (怎麼又、又犯了、一直犯同樣的錯、講過了), or asks to turn a rule into a check (把這個變成檢查、加個 lint). It MUST NOT answer a repeated mistake with only a new line in a rules file or a memory entry when a stronger level is available."
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
metadata:
  version: "1.0.0"
---

## Overview

A written rule depends on someone reading it at the right moment. When a mistake has already happened twice, the rule has been tried. Change the project so the next agent or person cannot make the mistake, or is stopped the moment they do.

## Step 1 — Name the mistake class

Collect the occurrences from **project-memory**, commits and reverts, review comments, the user's corrections in this conversation, and comments that explain a workaround. Group them by what went wrong, not by where. A class counts once it has happened twice.

For each class write one sentence: what is done wrong, and what should be done instead.

## Step 2 — Fix it at the highest level that works

Go down this list and stop at the first level that can carry the rule.

| Level | What it means | Examples |
|---|---|---|
| 1. Structure | The wrong thing is no longer possible | One supported way to do the task; one owner for each piece of state; one source of truth in place of lists kept in sync by hand; the old path and the dead code an agent would copy are deleted |
| 2. A check that fails | The wrong thing is written and then rejected, with an error that names what to do instead | A type or schema that cannot hold the bad state; a lint rule; a CI step; a pre-commit or agent hook; a script the project runs after every change |
| 3. A test | The behavior is pinned | A test that fails when the behavior breaks and keeps passing when only the internals change |
| 4. A written rule | Nothing fails when it is skipped | An entry in `AGENTS.md` or **project-memory**. Use this level only for judgment calls that no check can make |

Say for each class which level was chosen and why the level above it does not work.

A check that changes CI, shared lint configuration or hooks affects everyone working in the project. Propose it with what it will reject, and get the user's go-ahead before adding it.

## Step 3 — Prove the check

Run the new check against a real past occurrence and show that it fails there, then show that it passes on the corrected version. A check that has never been seen to fail is not evidence. The same command runs locally and in CI.

An exception to a check goes on the offending line, with the reason.

## Step 4 — Record what enforces what

Record through **project-memory** one entry per class: the rule in one sentence and what enforces it. When an existing entry describes a rule that nothing enforced and the mistake happened again, add the entry again under the same key with what now enforces it. Once the mistake can no longer happen, add it again under the same key saying so and naming the check; the store is append-only, so nothing is deleted.

## Report

For each class: the occurrences found, the level chosen and why not a higher one, what was added, and the output showing the check failing on the past occurrence.
