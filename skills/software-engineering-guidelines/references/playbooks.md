# Playbooks

One ordered list of steps for each kind of task. At the start of a task, pick the one that matches, copy its steps into the task list word for word, and work through them in order. A step that does not apply stays in the list as `skip: <reason>`; it is not deleted.

Pick by what the task is. Use Small change only when the change meets the definition of small and low-risk in the core's [Independent Review](../SKILL.md#independent-review). When two playbooks fit, use the one with more steps. Skills named in a step are loaded at that step.

## Feature

New or changed behavior.

1. Read this project's memory. The session-start hook provides it; when it is absent or lists keys only, load it through **project-memory**.
2. Restate the goal and the smallest change that meets it. List what is asked, including the [Counterpart Operations](../SKILL.md#counterpart-operations). Settle the choices only the user can make; use **eng-architect** when architecture or the split into tickets is undecided.
3. Set the success criteria and choose the verification. Apply test-first when the change is large ([testing.md](testing.md)). Read [design.md](design.md).
4. Write the skeleton ([Skeleton First](../SKILL.md#skeleton-first)) and decide for each slot whether to dispatch it.
5. Fill the slots. A failure whose cause is not established goes to **investigate** before any fix. A change to an existing API goes through **agent-delegation** first.
6. Verify with **test-and-fix**.
7. Have the diff reviewed through **diff-review** when the change is substantial or high-risk, or about to become a PR, MR or merge. A small, low-risk change gets its lightweight self-review.
8. When the work is substantial, have the result checked against the request through **acceptance-review**.
9. Go through the Pre-Ship Checklist. Commit under [Staging and Commits](../SKILL.md#staging-and-commits); push, open a PR or MR, or merge through **ship-it**.
10. Record qualifying lessons through **project-memory**.
11. Compare the result with the full authorized outcome and continue any required work that can still be completed. Then give the [Turn-End Report](../SKILL.md#turn-end-report).

## Bug fix

Something that worked, or should work, does not.

1. Read this project's memory, and search it for the symptom.
2. Reproduce the failure on the real target and write down the exact symptom.
3. Establish the root cause. When it is not already shown by evidence, use **investigate**.
4. Write the fix skeleton: the root cause, every place that has the same fault, and the check that proves each one. Check what the fix could break elsewhere with **diff-review**'s blast-radius check.
5. Add the [regression test](../SKILL.md#regression-tests) and make the fix.
6. Verify with **test-and-fix**, and repeat the original reproduction.
7. Have the diff reviewed through **diff-review** when the change is substantial or high-risk, or about to become a PR, MR or merge. A small, low-risk change gets its lightweight self-review.
8. When the work is substantial, have the result checked against the request through **acceptance-review**.
9. Commit the fix, then its test, under [Staging and Commits](../SKILL.md#staging-and-commits); deliver through **ship-it**.
10. When this is the second time the same kind of mistake happened, use **prevent-recurrence**.
11. Record qualifying lessons through **project-memory**.
12. Compare the result with the full authorized outcome and continue any required work that can still be completed. Then give the [Turn-End Report](../SKILL.md#turn-end-report).

## Refactoring

Structure changes, behavior does not.

1. Read this project's memory.
2. State what must stay the same, and run the relevant tests to record their results before changing anything.
3. Check what the change could break elsewhere with **diff-review**'s blast-radius check.
4. Change in small units that each end in a state the tests can check.
5. Run the same tests again and compare with step 2.
6. Have the diff reviewed through **diff-review** when the change is substantial or high-risk, or about to become a PR, MR or merge. A small, low-risk change gets its lightweight self-review.
7. When the work is substantial, have the result checked against the request through **acceptance-review**.
8. Commit under [Staging and Commits](../SKILL.md#staging-and-commits); deliver through **ship-it**.
9. Record qualifying lessons through **project-memory**.
10. Compare the result with the full authorized outcome and continue any required work that can still be completed. Then give the [Turn-End Report](../SKILL.md#turn-end-report).

## Investigation

A question to answer. Nothing is changed.

1. Read this project's memory.
2. Restate the question and what a complete answer contains.
3. Gather evidence with file and line, command output or source for each point. For a failure, follow **investigate** as far as naming the cause, and stop before its fix step. When the user wants it fixed, switch to Bug fix.
4. Label each statement under [Evidence for Claims](../SKILL.md#evidence-for-claims): checked, or hypothesis.
5. Answer the question. Change no file.
6. Record qualifying lessons through **project-memory**.
7. Compare the result with the full authorized outcome and continue any required work that can still be completed. Then give the [Turn-End Report](../SKILL.md#turn-end-report).

## Small change

A few lines, easy to revert, no shared contract, nothing high-impact or security-relevant.

1. Confirm the change meets the definition; otherwise switch to Feature or Bug fix.
2. Make the change.
3. Check what it could break elsewhere with **diff-review**'s blast-radius check.
4. Run the tests and checks that cover it.
5. Do the lightweight self-review in **diff-review**.
6. Commit under [Staging and Commits](../SKILL.md#staging-and-commits).
7. Record qualifying lessons through **project-memory**.
8. Compare the result with the full authorized outcome and continue any required work that can still be completed. Then give the [Turn-End Report](../SKILL.md#turn-end-report). Say that the review was a self-review.
