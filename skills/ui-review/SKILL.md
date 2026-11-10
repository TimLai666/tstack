---
name: ui-review
description: "Review a built user interface as it actually renders: score it, scan for generic AI-made patterns, and check it against the project's design baseline. This skill MUST be used when the user asks for a UI review, a design review of implemented screens, or an AI slop scan, and for the screens a diff changed. It SHOULD be used after screens are implemented or changed, before the work is handed back. It MUST inspect rendered screens and MUST NOT judge from source code or design files alone, and MUST NOT be used to set a design direction or to change DESIGN.md. Triggers on: UI 審查、畫面審查、介面審查、看一下做出來的畫面、design review、UI review、AI slop scan"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
metadata:
  version: "1.2.2"
---

## Overview

Review what was built, as the user will see it: the running interface against the project's design baseline. Report scored findings with evidence from the rendered screens, and update the review record when one is kept.

| Review of | Skill |
|---|---|
| Rendered screens and interactions | this skill |
| Code logic and implementation | **diff-review** |
| Vulnerabilities | **security-scan** |

When this conversation built or changed the screens under review, who reviews them follows the core's [Independent Review](../software-engineering-guidelines/SKILL.md#independent-review), including its exception for a small, low-risk change. A reviewer dispatched for this purpose reviews the screens itself and dispatches no one.

When the review is for a diff handed over by **diff-review**, cover only the screens that diff changed and return the findings.

A review request produces findings and recommendations. Fix only when the user asked for fixes, then recheck the affected screens in the rendered result.

## Step 0 — Establish the baseline and look at the screens

Confirm the project root and locate the design sources for the screens under review, using project instructions and actual content. Read the applicable design baseline and the existing review record, including score history and unresolved findings. Follow relevant sections and references rather than limiting discovery by file count or assuming fixed headings.

A `DESIGN.md` found here is **input, not output**: read it and score against its tokens; never overwrite it. This skill writes `DESIGN-REVIEW.md` instead (Step 4).

Inspect the actual rendered screens and exercise the relevant interactions at the viewport sizes and states under review. Source code and design documents support this inspection; they do not substitute for viewing the rendered result. Record which screens, states, and interactions were checked. If rendering or interaction is unavailable, state the missing evidence and leave affected judgments unverified.

Compare previous findings with the current rendered behavior and implementation evidence. An unchanged score alone does not establish that a fix was not applied. Distinguish unresolved findings, partial improvements, and new issues.

## Step 1 — Rate each dimension

For each of the 10 dimensions, give a score from 0 to 10 and describe what a 10 would look like:

| Dimension | Score | Current state | What 10 looks like here |
|-----------|-------|---------------|-------------------------|
| Hierarchy | ? | [describe] | One unmistakable primary action per screen |
| Whitespace | ? | | Elements breathe; nothing fights for space |
| Typography | ? | | Clear weights; size conveys importance only |
| Color | ? | | Semantic colors; each has a job; AA contrast |
| Consistency | ? | | Same component = same interaction everywhere |
| Copy | ? | | Every label names the action, not the widget |
| Empty states | ? | | Designed as onboarding, not error fallback |
| Error states | ? | | Human language; tells you what to do next |
| Motion | ? | | Purposeful only; explains state change |
| Mobile | ? | | One-thumb usable; touch targets >=44px |

## Step 2 — AI slop scan

Flag any present:
- labels: "Submit", "OK", "Cancel"
- empty states with no CTA or guidance
- errors like "An error occurred" or "Something went wrong"
- spacing off the 4px grid, or inconsistent between similar elements
- generic hero sections with gradient backgrounds and floating 3D icons
- every section a full-width card, shadow stacked on shadow
- cards nested inside cards inside cards
- gradient on gradient color schemes
- no hierarchy
- inline-able flows forced into modals
- tables with more than 6 columns shown by default
- loading states that are only a spinner
- success states that only say "Success!" with no next step

## Step 3 — Present findings and decisions

Report each finding in the format and scale of the core's [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity), with the screen and state as its location. Levels for rendered UI:

| Level | Rendered UI |
|---|---|
| P0 | The primary action cannot be completed, or content is unreadable or unusable at a supported viewport |
| P1 | The user is misled, or an important state such as error, empty or loading is broken or missing |
| P2 | An inconsistency between similar elements, or a deviation from the design baseline |
| P3 | Polish |

Present findings and recommended fixes with evidence from the inspected screens and interactions. Ask about unresolved tradeoffs or changes to an agreed direction, and group related choices with a recommendation. Execute fixes only within the user's authorized scope. After an authorized UI fix, inspect the rendered result again and repeat the affected interactions before marking the finding resolved.

## Step 4 — Update DESIGN-REVIEW.md

Use the existing project review record. When a persistent review is requested and no arrangement exists, write `DESIGN-REVIEW.md` to the project root; otherwise deliver the review directly. The filename below refers to the chosen review record. **Never write `DESIGN.md`**; that filename belongs to `design-studio`.

`DESIGN-REVIEW.md` is a **state file**: one per project, updated in place, no date or branch in the filename. Prior scores stay in the score history table; git holds the rest.

Update, do not replace:

| Section | On re-review |
|---|---|
| Score history | Append one row. Never rewrite past rows |
| Dimension scores | Overwrite with the current scores |
| Open slop flags | Keep only what is still unresolved. Delete the ones that got fixed |
| Component spec | Accumulate. Existing components stay unless the component itself is gone |

```markdown
# Design Review: [project]
_Last reviewed: [date] - ui-review - [branch]_

## Score history
| Date | Hier | White | Type | Color | Consist | Copy | Empty | Error | Motion | Mobile |
|------|------|-------|------|-------|---------|------|-------|-------|--------|--------|
[one row per review, oldest first]

## Dimension scores
| Dimension | Score | Notes |
|-----------|-------|-------|
[table]

## Open slop flags
[unresolved only]

## Component spec

### [Component name]
- **Copy:** [exact labels, error messages, empty states, tooltips]
- **States:** default | hover | active | disabled | loading | error | empty
- **Mobile:** [specific behavior]
- **Touch target:** [size in px]

## Token conformance
| Token | Design baseline value | Used as | Verdict |
|-------|-----------------|---------|---------|
[one row per violation only — matches are not worth listing]

## Motion
| Trigger | Animation | Duration | Purpose |
|---------|-----------|----------|---------|
```

Use the project's established visual specification, whether it is `DESIGN.md` or an equivalent source. Reference its actual location when assessing conformance; keep design-system definitions in that source rather than creating a second set in the review record.

If no applicable baseline can be found, state that limitation and leave baseline-dependent scores ungraded. Report observable issues supported by rendered-screen evidence, and recommend establishing the missing visual specification when needed. The absence of the filename `DESIGN.md` alone does not establish that no baseline exists.

## Completion check

- Findings come from actual rendered screens and exercised interactions, with the screens, states and viewport sizes that were inspected listed.
- Screens or states that could not be rendered or viewed are reported as not reviewed, with the reason.
- Authorized fixes were rechecked in the rendered result.
- The review record, when kept, was updated in place and unrelated content preserved. `DESIGN.md` was not modified.
