# Reviewer isolation

Follow this file before dispatching any review.

## Reviewer isolation

Whose work MUST go to an independent reviewer follows the core [Independent Review](../../software-engineering-guidelines/SKILL.md#independent-review). This section sets how to isolate. The reviewer MUST be isolated from the context of the author of the work under review, including the main conversation when the main agent implemented it itself. You MUST NOT rename the author's agent or session, change its role or tell it to ignore earlier messages and then use it to review, and MUST NOT bring that context in through session inheritance or by reposting the implementation discussion. Roles required to be independent of each other MUST NOT share a context, even when they run at different times. This rule applies to both built-in tools and external CLIs.

An ordinary review provides the requirements, acceptance criteria, code, diff and checkable verification evidence. An existing reviewer may be reused only when it has not been given the implementation context of the work under review and this review does not need to be isolated from the previous review.
