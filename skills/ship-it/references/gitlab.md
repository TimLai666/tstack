# GitLab commands

The commands for each ship-it step when the remote is on GitLab, using `glab`. Read `glab <subcommand> --help` before using a flag that is not shown here.

| Step | Action | Command |
|---|---|---|
| 4 | Pipeline for a commit | `glab api "projects/:id/pipelines?sha=$_SHIP_SHA"` |
| 7 | Create the MR | `glab mr create --target-branch "$_SHIP_BASE" --source-branch "$_SHIP_BRANCH" --title "$_SHIP_TITLE" --description-file "$_SHIP_BODY"` |
| 7 | Update the MR | `glab mr update` with the completed description |
| 8 | Head commit SHA | `glab mr view <number> --output json` (`sha`) |
| 8 | Every check | `glab api "projects/:id/pipelines?sha=$_SHIP_SHA"`, then each pipeline's jobs with `glab api "projects/:id/pipelines/<pipeline id>/jobs"` |
| 8 | Review comments | `glab mr view <number> --comments` |
| 8 | Merge now | `glab mr merge <number> --sha "$_SHIP_SHA" --auto-merge=false --yes` |
| 8 | Let the platform merge | `glab mr merge <number> --sha "$_SHIP_SHA" --auto-merge --yes` |
| 9 | Read the checks | `glab ci status --branch "$_SHIP_BRANCH"` |
| 9 | Watch the checks | `glab ci status --branch "$_SHIP_BRANCH" --wait` |

Always state the auto-merge choice. `glab mr merge` without it turns auto-merge on by default, and with no pipeline it merges at once.

When the head commit has more than one pipeline, each of them must be green, counting the latest run of one that was run again.

## When the platform may do the waiting

GitLab's auto-merge waits for the pipeline of the head commit. That pipeline still counts as succeeded when a job marked as allowed to fail has failed.

Use `--auto-merge` only when no job in the pipeline is allowed to fail, the commit has a single pipeline, and no automated review is expected. Otherwise wait yourself and merge when the head commit is green.
