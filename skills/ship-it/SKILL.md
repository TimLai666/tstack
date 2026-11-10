---
name: ship-it
description: "Deliver committed work on GitHub or GitLab: stage and push, open or update a pull request or merge request, and merge. This skill MUST be used when pushing after a commit, opening or updating a PR or MR, merging one, or when the user invokes ship-it (push、推上去、推到 dev、開 PR、開 MR、準備 PR、合併、merge、整理分支交付). It SHOULD be used when the user asks to prepare a completed feature for review. A push runs the light path; a PR, MR or merge runs the full path. It MUST NOT merge before the pipeline for the exact head commit has succeeded, and MUST NOT be skipped because the change is small. Commit message format belongs to software-engineering-guidelines; releases and deployments are covered only when the user asks to verify them."
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - AskUserQuestion
metadata:
  version: "2.1.0"
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
the CLI's `--help` for the subcommand before using a flag this skill does not
show. On another platform, use its authorized CLI or API and apply the same
gates.

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

Sort every modified and untracked file into this delivery or not. Before
committing, list the files that are left out and why. Do not silently stash,
discard or include unrelated changes.

Stage with explicit paths only. `git add -A`, `git add .`, `git add --all`,
`git commit -a` and `git commit -am` are not used, including in a fresh
repository: list the paths. Leave out build output, caches, operating-system
metadata files and binaries the task did not ask for.

```bash
git add -- <path> <path>
git diff --cached --stat
```

When creating commits, follow the [commit-message rules](../software-engineering-guidelines/SKILL.md#commit-messages) before writing the message.

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
their locations without reproducing secret values.

## Step 4 — Push and read the pipeline once

```bash
git push "$_SHIP_REMOTE" "$_SHIP_BRANCH"
_SHIP_SHA=$(git rev-parse HEAD)
```

Look up the pipeline for `_SHIP_SHA` and report it as passed, failed, running or
absent, with its URL:

| Platform | Pipeline for a commit |
|---|---|
| GitHub | `gh run list --commit "$_SHIP_SHA"` |
| GitLab | `glab api "projects/:id/pipelines?sha=$_SHIP_SHA"` |

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

Run **diff-inspector** on the outgoing diff unless an existing review covers
that same diff. Review later changes and their effects. Resolve confirmed
findings according to severity and project rules, and distinguish unresolved
questions from confirmed defects.

When the diff changes rendered screens, run **ui-review** on those screens
unless an existing review covers their current state.

## Step 7 — Open or update the PR or MR

Push as in Step 4. Check for an existing PR or MR for the branch before creating
one. Follow the repository's template. If none exists, use
[the PR body template](assets/pr-body.md), filling it with actual changes and
verification results. Scale detail to the change and remove irrelevant sections.

**Do not append co-author credits, `Co-authored-by` trailers or agent signatures
to PR or MR titles or descriptions.**

Save the completed body to a temporary file and use its path as `_SHIP_BODY`.
Set `_SHIP_TITLE` from the actual change:

| Platform | Create | Update |
|---|---|---|
| GitHub | `gh pr create --base "$_SHIP_BASE" --head "$_SHIP_BRANCH" --title "$_SHIP_TITLE" --body-file "$_SHIP_BODY"` | `gh pr edit` with the body file |
| GitLab | `glab mr create --target-branch "$_SHIP_BASE" --source-branch "$_SHIP_BRANCH" --title "$_SHIP_TITLE" --description-file "$_SHIP_BODY"` | `glab mr update` with the completed description |

If the CLI is unavailable or unauthenticated, use an available authorized
alternative or provide the completed title and body for manual submission.
Report which operations actually succeeded.

## Step 8 — Merge only on a successful pipeline

Merge only when the user or the project's recorded rule authorizes it.

1. Read the head commit SHA of the PR or MR from the platform, not from the local branch.
2. Read the pipeline for that exact SHA. Only `success` allows a merge. Running, failed, cancelled, skipped and absent all mean not verified: no pipeline for the head commit is not a pass.
3. Merge with the SHA pinned, so a commit pushed in between cannot ride along.

| Platform | Head SHA | Merge |
|---|---|---|
| GitHub | `gh pr view <number> --json headRefOid` | `gh pr merge <number> --match-head-commit "$_SHIP_SHA"` |
| GitLab | `glab mr view <number> --output json` (`sha`) | `glab mr merge <number> --sha "$_SHIP_SHA" --auto-merge=false --yes` |

Do not let the platform decide for you. `glab mr merge` turns auto-merge on by
default and can merge while no pipeline exists yet; `gh pr merge --auto` hands
the decision to branch rules. Use an auto-merge option only when the user asked
for it, and say that the merge has not happened yet.

When the pipeline is still running and waiting is part of the request, wait for
its result and then repeat this step from item 1.

## Step 9 — Check CI and deployment, record lessons

Read the checks for the resulting PR, MR or merge commit and report passed,
failed, pending or unavailable. When waiting for required CI is part of the
requested delivery, watch it to a result and handle failures within scope:

| Platform | Read | Watch |
|---|---|---|
| GitHub | `gh pr checks "$_SHIP_PR_URL"` | `gh pr checks "$_SHIP_PR_URL" --watch` |
| GitLab | `glab ci status --branch "$_SHIP_BRANCH"` | `glab ci status --branch "$_SHIP_BRANCH" --wait` |

When deployment verification is requested, identify the deployment run or job
for the intended revision and environment and watch that one explicitly, for
example `gh run watch "$_SHIP_RUN_ID" --exit-status`.

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
