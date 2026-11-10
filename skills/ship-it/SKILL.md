---
name: ship-it
description: "Deliver committed work on GitHub or GitLab: push, open or update a PR or MR, and merge. This skill MUST be used when pushing after a commit, opening or updating a PR or MR, or merging, and MUST NOT be skipped because the change is small. It SHOULD be used when the user asks to prepare a completed feature for review. It MUST NOT merge before every check on the exact head commit has passed and automated review feedback is resolved. Triggers on: push、推上去、推到 dev、開 PR、開 MR、準備 PR、整理分支交付、合併、merge、全綠後合併、ship-it"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - AskUserQuestion
metadata:
  version: "3.0.1"
---

## Overview

Delivery has two paths. Pick by what is about to happen, and run every step of the chosen path.

| About to | Path | Steps |
|---|---|---|
| Push commits to a branch, with no PR or MR involved | Light | 1 to 4 |
| Open or update a PR or MR, or merge one | Full | 1 to 9 |

## Step 1 — Confirm scope, platform and project rules

Read the project's coordination and delivery instructions and its saved project
memory. Confirm the requested outcome, current branch, target remote and base
branch from repository settings and user intent; do not guess `main` when the
base is unknown.

Commit, push, opening a PR or MR, and merging are separate authorizations. Take
each from the user's request or the project's recorded rule. Permission for one
does not grant the next.

Identify the hosting platform from the target remote's URL and use that
platform's CLI for every later step: `gh` for GitHub, `glab` for GitLab. Read
that platform's command file once: [references/github.md](references/github.md)
or [references/gitlab.md](references/gitlab.md). Later steps name an action, and
the command for it is in that file. On another platform, use its authorized CLI
or API and apply the same gates.

Use the project's existing delivery document. With no other arrangement, look
for `delivery-status.md`; support `delivery-plan.md` in older projects. Read the
current phase, expected output and acceptance requirements, not just the first
few lines. If the diff conflicts with the agreed scope, resolve that decision
with the user before shipping. Do not create a status file just for this check.

If `delivery-plan.md` exists, follow the [legacy status migration rules](../eng-architect/references/legacy-status-migration.md) to check the saved decision, ask when unresolved, and record the user's choice before changing the status arrangement.

Small authorized changes may go on the current branch when the project allows
it. Larger or riskier work on the base branch gets a suitable branch first,
without resetting existing work. When another session or agent is changing the
same repository, work in a separate worktree.

## Step 2 — Stage and commit by explicit path

```bash
git status --short
```

Sort every modified and untracked file into this delivery or not, then stage
and commit under the core's [Staging and Commits](../software-engineering-guidelines/SKILL.md#staging-and-commits).

```bash
git add -- <path> <path>
git diff --cached --stat
```

## Step 3 — Check the target before pushing

After setting `_SHIP_REMOTE`, `_SHIP_BASE` and `_SHIP_BRANCH` to verified values:

```bash
git fetch "$_SHIP_REMOTE" "$_SHIP_BASE"
git diff "$_SHIP_REMOTE/$_SHIP_BASE...HEAD" --stat
git log "$_SHIP_REMOTE/$_SHIP_BASE..HEAD" --oneline
```

Read the latest pipeline of the branch being pushed to. When it has failed, fix
that failure first, or confirm this push is the fix. Do not stack unrelated
commits on a red branch.

Scan the outgoing commits and diff for secrets, including keys, tokens,
credentials and sensitive connection strings. If found, stop the push and report
them as the core's [Secrets](../software-engineering-guidelines/SKILL.md#secrets) rule requires.

## Step 4 — Push and read the pipeline once

```bash
git push "$_SHIP_REMOTE" "$_SHIP_BRANCH"
_SHIP_SHA=$(git rev-parse HEAD)
```

Look up the pipeline for `_SHIP_SHA` and report it as passed, failed, running or
absent, with its URL.

A failed pipeline caused by this push is handled now, within scope. The light
path ends here; report with the Delivery report below.

## Step 5 — Sync when needed

Check whether the branch needs the updated base. Follow the project's merge or
rebase convention; do not automatically merge the base into every branch. Avoid
rewriting shared history without authorization.

Resolve conflicts from the intended behavior and both sides' changes, then
validate the resolution. Ask only when a material behavior or scope decision
cannot be determined from available evidence.

## Step 6 — Verify like CI and review the final diff

Run the steps the project's CI runs that decide a merge, in the same way CI runs
them: a clean install from the lockfile, the build, and the integration tests,
along with tests appropriate to the changes and risks. Run the project's full
suite according to its rules. Follow **test-and-fix** for what counts as
verified. Reuse prior results only when they cover the current code and relevant
environment; rerun affected checks after subsequent edits or conflict resolution.

Check coverage of important behavior, boundary conditions and error handling.
Add meaningful tests where those behaviors lack evidence, rather than requiring
a test for every new code path or testing implementation details alone.

Fix failures introduced by this branch. Establish evidence for pre-existing
failures or environment blockers, apply project delivery rules, and report any
remaining gate instead of presenting partial results as a pass.

Run **diff-review** on the outgoing diff unless an existing review covers
that same diff. Review later changes and their effects. Resolve confirmed
findings according to severity and project rules, and distinguish unresolved
questions from confirmed defects.

## Step 7 — Open or update the PR or MR

Push as in Step 4. Check for an existing PR or MR for the branch before creating
one. Follow the repository's template. If none exists, use
[the PR body template](assets/pr-body.md), filling it with actual changes and
verification results. Scale detail to the change and remove irrelevant sections.

**Do not append co-author credits, `Co-authored-by` trailers or agent signatures
to PR or MR titles or descriptions.**

Save the completed body to a temporary file and use its path as `_SHIP_BODY`.
Set `_SHIP_TITLE` from the actual change:

Create the PR or MR, or update the existing one, with the platform's command.

If the CLI is unavailable or unauthenticated, use an available authorized
alternative or provide the completed title and body for manual submission.
Report which operations actually succeeded.

## Step 8 — Merge only when everything is green

Merge only when the user or the project's recorded rule authorizes it. A request such as「全綠之後合併」is that authorization, and it is not finished until the PR or MR is confirmed merged.

### What green means

Green is judged for the exact head commit of the PR or MR, and all of these hold:

- **Every check has finished and none failed**, whether the platform marks it required or not. A check that was skipped by its own conditions or reported neutral does not count against it. A pipeline in which nothing ran is not green. When the head commit has more than one pipeline, each of them must be green.
- **Automated review feedback is dealt with.** When a review agent or bot comments on PRs or MRs in this repository, wait for its review of this head commit and resolve every point it raises: fix it, or reply with the reason it does not apply. A fix is a new commit, so green is judged again from the start.
- **A review agent that cannot review is not waited for.** When it reports that it could not run, for example because its quota or usage limit is exhausted, go on without it and say so in the report. When it is simply silent after every check has finished, this is not green: do not merge, report that its review has not arrived, and ask how to proceed.

### Merging

1. Read the head commit SHA from the platform, not from the local branch, and set `_SHIP_SHA` to that value for the commands below.
2. Read every check for that SHA and the review comments on the PR or MR.
3. Act on what they show:

| State for the head SHA | Do |
|---|---|
| Green | Merge now, pinned to the SHA |
| Checks still running, or an automated review still expected | Wait as described below. Say that it has not merged yet |
| A check failed or was cancelled, a review point is unresolved, or a pipeline exists in which nothing ran | Do not merge. Handle it within scope or report it |
| No pipeline exists yet | Do not merge and do not set auto-merge: with no pipeline the platform merges at once. Wait for the pipeline to appear, then start again from item 1 |

Always pin the SHA, so a commit pushed in between cannot ride along.

### Waiting

Letting the platform merge keeps a merge-when-green request alive even if this conversation ends, but the platform only waits for what it knows about. Use it only when its condition is the same as green. The platform's command file says what that platform waits for and when it may be used.

Otherwise wait yourself: watch the checks in the background with the Step 9 watch command, and when it returns start again from item 1. The watch is only a signal that something finished. What decides is the state read for the pinned SHA at that moment.

After letting the platform merge, watch the same way and then confirm the PR or MR state. Merged ends the task. A failed check means nothing was merged: handle it within scope and repeat this step.

Until the merge is confirmed, name the pending merge in the core's [Turn-End Report](../software-engineering-guidelines/SKILL.md#turn-end-report).

## Step 9 — Check CI and deployment, record lessons

Read the checks for the resulting PR, MR or merge commit and report passed,
failed, pending or unavailable. When waiting for CI is part of the
requested delivery, watch it to a result and handle failures within scope:

When deployment verification is requested, identify the deployment run or job
for the intended revision and environment and watch that one explicitly.

Inspect failed checks or jobs and resolve failures within scope; when the cause
is not evident, invoke **investigate**. Verify the deployment's required outcome
before reporting success; a passing unrelated workflow is not deployment
evidence. If monitoring is blocked or interrupted, report the last observed
state, the PR, MR or run URL, and what remains unverified.

Run **project-memory** at this wrap-up checkpoint, following its recording
criteria. Save qualifying project-specific lessons and report saved entries.
If nothing qualifies, no announcement is needed.

## Delivery report

Report the path taken, the branch and scope, files left out of the commit,
actual test and review results, the PR or MR URL, the pipeline state for the
delivered commit, and unresolved requirements. Distinguish committed, pushed, PR
or MR created or updated, merged, and deployed based on evidence. Creating a PR
or MR does not establish merge or deployment.
