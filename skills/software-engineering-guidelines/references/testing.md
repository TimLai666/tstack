# Testing strategy

The short form of these rules is in [SKILL.md](../SKILL.md). Regression tests are defined there, under Shared Conventions.

**Choose verification that demonstrates the change works and matches its impact.**

Baseline rule:

- Every behavior-changing change needs test coverage.
- For text, formatting, or documentation changes, use checks suited to the affected content.
- Run the full test suite according to the project's rules.
- Before a check writes to an external system, confirm that a test environment exists and how the written data will be removed. With neither, do not write to it for verification; ask the user how to verify.
- Run the project's linter and type checker when provided, and report their results alongside the tests. Unresolved failures mean verification is incomplete.
- For small, local, low-risk fixes, add/update tests around the change (before or immediately after implementation is acceptable if justified).
- For large changes, broad-scope changes, or major new features, you MUST apply TDD: write the failing test first, then implement — don't write code and backfill tests.

A change is large when any one of these holds:

1. It touches several modules or layers (for example, UI, API and data layer change together).
2. It changes a public behavior boundary, such as an API contract, data model, access rule or core flow.
3. It adds a core new feature, or refactors a high-risk path (payment, authentication, permissions, data migration, state transitions).

Rules:

- **Before refactoring, establish the result of relevant tests; rerun them after the change.**
- **Don't weaken a test just to make it pass.** Unless the test itself is wrong.
- **For behavior-changing edits to skills, prompts, or agent workflows, compare the current and candidate versions on the same tasks in fresh contexts with the same model, tools, data access, and resource limits.** Scale the comparison to the change. Inspect actual decisions, artifacts, acceptance results, unsupported retries, premature stops, and cost. Keep acceptance cases separate from cases used to revise the instructions. Retain the current version as an eligible outcome; inconclusive comparisons do not establish improvement.
