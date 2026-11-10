# Technical review checklist

Whoever actually reviews the diff reads this: a dispatched reviewer, or the main conversation when it had no part in the diff. Report what you find in the format given in [SKILL.md](../SKILL.md#findings).

## Code

Review the full diff. For each applicable area, verify:

- **Queries and data integrity:** Queries remain bounded, return the intended rows, and preserve data integrity across writes and transactions.
- **Race conditions and state:** Concurrent operations, check-then-act flows, shared state, and asynchronous work remain atomic and consistent.
- **Error handling:** Failures are surfaced and handled, including partial failures, timeouts, cleanup, and recovery.
- **Performance and resources:** Check unbounded work, resource leaks, N+1 queries, missing indexes, avoidable quadratic work, expensive loops, heavy dependencies, and fetch waterfalls.
- **Maintainability:** Check unnecessary complexity, duplicated logic, unclear responsibilities, leaky abstractions, and difficulty understanding, testing, or extending the change.
- **Data migration:** Check irreversible migrations, locking schema changes, missing foreign-key indexes, unsafe backfills, and removal of schemas before dependent code.
- **Completeness and compatibility:** For each changed shared contract, such as a state, field, path, identifier, schema, or configuration:
  1. Inventory relevant occurrences first: search the entire target tree using stable contract fragments such as path prefixes, filename patterns, field names, command names, or resolver functions.
  2. Trace each producer to all consumers and each consumer back to a concrete producer, including unchanged files outside the diff. A consumer has a concrete producer only when it computes the value or calls a named shared resolver. Prose placeholders, examples, and state expected from an earlier tool do not count.
  3. Compare the exact values or derivation logic used on both sides. Report unaccounted occurrences, missing implementations, and duplicated or divergent derivations.
- **API contracts:** Check incompatible responses, new required inputs without defaults, changed error formats, and pagination behavior using the compatibility tracing above.
- **Tests:** Tests demonstrate changed public behavior, negative and edge cases, failure paths, and regression protection. Check isolation violations and flaky patterns.

## Documentation and guidance consistency

Review documentation and distributable guidance affected by the diff, both at the repository root and within affected packages, modules, or subtrees. Include, where applicable:

- README files, architecture guides, contributing guides, API references, and other explanatory documentation
- Package- or module-specific documentation
- Changelogs and release notes when required by project convention or when the change affects users
- Repository operating contracts for agents working in the repository, such as `AGENTS.md` or `CLAUDE.md`
- Installable agent skills, prompts, templates, examples, plugin metadata, and other agent-facing artifacts distributed by the repository

Check whether changes to behavior, interfaces, setup, configuration, installation, migrations, required artifacts, workflows, handoff rules, tool usage, or deployment constraints are reflected in every affected document or artifact.

When the repository distributes installable skills or other agent-facing artifacts, treat them as product outputs. Verify that their instructions, examples, references, metadata, and packaging remain aligned with the changed behavior.

Report each mismatch with references to both the changed code and the affected document or artifact.
