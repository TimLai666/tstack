# Follow-ups

Discovered during development, waiting for user decision.

Resolved items should be deleted from this list.

### [2025-07-09] — Legacy auth middleware uses deprecated JWT library
- **Where**: `src/middleware/auth.ts`
- **What**: Uses `jsonwebtoken` v8 which has known CVEs. Current task is unrelated to auth.
- **Suggestion**: Upgrade to `jose` or `jsonwebtoken` v9. Migration is isolated to this file.
- **Status**: pending

### [2025-07-09] — N+1 query in user list endpoint
- **Where**: `src/routes/users.ts:42`
- **What**: `GET /users` loads each user's posts in a loop. 100 users = 101 queries.
- **Suggestion**: Use `JOIN` or batch load with `WHERE id IN (...)`. Low risk, self-contained fix.
- **Status**: decided
- **Decision**: Do it now — add it to current sprint.
