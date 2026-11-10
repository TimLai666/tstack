# GitHub commands

The commands for each ship-it step when the remote is on GitHub, using `gh`. Read `gh <subcommand> --help` before using a flag that is not shown here.

| Step | Action | Command |
|---|---|---|
| 4 | Pipeline for a commit | `gh run list --commit "$_SHIP_SHA"` |
| 7 | Create the PR | `gh pr create --base "$_SHIP_BASE" --head "$_SHIP_BRANCH" --title "$_SHIP_TITLE" --body-file "$_SHIP_BODY"` |
| 7 | Update the PR | `gh pr edit` with the body file |
| 8 | Head commit SHA | `gh pr view <number> --json headRefOid` |
| 8 | Every check | `gh pr checks <number>` |
| 8 | Review comments | `gh pr view <number> --json reviews,comments`, and `gh api repos/{owner}/{repo}/pulls/<number>/comments` for inline comments |
| 8 | Merge now | `gh pr merge <number> --match-head-commit "$_SHIP_SHA"` |
| 8 | Let the platform merge | `gh pr merge <number> --auto --match-head-commit "$_SHIP_SHA"` |
| 9 | Read the checks | `gh pr checks "$_SHIP_PR_URL"` |
| 9 | Watch the checks | `gh pr checks "$_SHIP_PR_URL" --watch` |
| 9 | Watch a deployment run | `gh run watch "$_SHIP_RUN_ID" --exit-status` |

## When the platform may do the waiting

GitHub's auto-merge waits for the branch's required checks and nothing else. When the branch has no required checks, it merges at once.

Use `--auto` only when every check that runs on the PR is a required check, and no automated review is expected. Otherwise wait yourself and merge when the head commit is green.
