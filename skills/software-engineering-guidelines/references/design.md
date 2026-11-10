# Designing before coding

Read before designing anything larger than a single-location change. The short form of these rules is in [SKILL.md](../SKILL.md).

## Think before coding

**Verify what you can. Make material assumptions and tradeoffs clear.**

Before implementing:

- Own the implementation design. Resolve routine technical details from the code, documentation, existing conventions, and focused checks. Use reasonable assumptions within the authorized scope, explaining them when they help the user assess the result. Do not turn internal design work into an exhaustive questionnaire or require approval for each implementation detail.
- Ask the user only when a gap remains after checking available information and would materially affect the result, scope, authorization, or an important tradeoff. Explain the relevant difference and recommend an approach. Continue independent work while that decision is pending.
- If a simpler approach exists, say so. Push back when warranted.
- Work out a coherent design for the full authorized outcome before filling individual components. Trace required flows through responsibilities, interfaces, data lifecycle, dependencies, failure and recovery behavior, and acceptance checks. Consider relevant boundary cases, duplicate or concurrent operations, interruption, compatibility, and downstream effects before coding. Scale the depth to the task and resolve foreseeable gaps before they become implementation rework.
- Compare materially different approaches against correctness, compatibility, maintainability, and actual resource constraints. Choose the simplest approach that satisfies the full agreed requirements. Validate uncertain assumptions that could invalidate it with focused checks, then proceed once material decisions have sufficient support. Apply the design and required quality from the first implementation. Revisit settled decisions when new evidence or changed requirements warrants it.

## Success criteria

**Define success criteria. Use observed progress to choose each next step.**

Transform tasks into verifiable goals — e.g. "Add validation" → "Write tests for invalid inputs, then make them pass".

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Derive concrete success criteria from the request and available project evidence. Resolve routine gaps yourself and apply Principle 1's clarification threshold to material unknowns.

## Whole-goal priority

- For multi-part work, identify the required outcomes, their dependencies, and which primary flows remain unimplemented or unverified. Choose the next work from these gaps before deepening an already working part.
- Implement production-intended components according to the agreed design, with the correctness and interfaces their role requires. Integrate and verify a complete primary flow early, then cover the remaining primary flows before optional local refinement. Do not substitute a knowingly inadequate design or disposable implementation for required work. Scaffolding, disconnected components, and mock outputs do not establish working coverage. Keep intermediate gaps explicit; complete all required edge cases and checks before delivery.
- Once a part meets the criteria needed for the current integrated flow, move to the next uncovered outcome or blocking dependency. Defer extra abstraction, optimization beyond the agreed target, cosmetic polish, and repeated passing checks unless new evidence justifies them. Complete necessary local work first when correctness, safety, data integrity, or a downstream dependency prevents valid integration.
- Follow an explicit user priority or narrowly scoped request. Do not expand the task to create breadth. Before returning to a covered part, identify the unmet requirement or new evidence that makes that work more valuable than the remaining gaps.
