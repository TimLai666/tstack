---
name: security-scan
description: "Find security vulnerabilities in code the user owns, then fix and verify them: a whole project, or one diff handed over by diff-review. This skill MUST be used when the user asks for a security scan, audit or hardening, and for the security part of a diff review. It SHOULD be used before a first public release and after adding authentication, payment, file upload or anything that takes outside input. It MUST fetch the current CWE Top 25, OWASP and related lists at scan time and MUST NOT rely on remembered editions. It MUST NOT be used against systems or code the user does not own or is not authorized to test. Triggers on: 資安掃描、資安審查、漏洞掃描、找漏洞、補漏洞、security scan、security audit"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
  - AskUserQuestion
  - WebFetch
  - WebSearch
metadata:
  version: "2.0.0"
---

# Security Scan

## Overview

Find and fix security vulnerabilities in code the user develops. Checks come from two sources: the latest public lists fetched at scan time (CWE Top 25, the OWASP lists and others), and this skill's [vulnerability catalog](references/vulnerability-catalog.md). Every finding needs a code location and a reproducible trigger. Verify again after the fix.

There are two modes:

| Mode | When to use | Scope |
|---|---|---|
| Whole project | The user asks for a scan or a health check | The whole project or the specified directories |
| diff | Handed over by **diff-review**, or the user wants the security of a diff, PR or MR checked | The diff, plus the existing code its inputs and outputs pass through |

This skill covers vulnerabilities only. Logic errors, implementation defects, performance and maintainability are reviewed by **diff-review**. Errors with an unknown cause go to **investigate**.

## Input Contract

| Item | How to determine it |
|---|---|
| Mode | diff mode when handed over by diff-review or when the user names a diff, PR or MR; whole-project mode otherwise |
| Scan scope | Whole-project mode: the directories, services or features the user specifies; the whole project when none is specified. diff mode: the specified diff and comparison base; when unclear, determine them from the git state and the target branch of the PR or MR |
| Authorization | The code is the user's own, or the user states they are authorized to test it. When this cannot be confirmed, ask first and do not start the scan |
| Whether to fix directly | When the user says to patch or fix, fix. When the user only says to scan or check, deliver the report first and fix after confirmation. diff mode only reports by default |
| Available test environment | Find how to start the project locally from its configuration and documentation. When no isolated environment is available, replace dynamic verification with static evidence and say so in the report |

## Workflow

### 1. Confirm scope and boundaries

- Read the project's rule files, architecture documents and existing security records. Load this project's memory with **project-memory**.
- Test only code and environments the user owns or is authorized to test. Reproduce vulnerabilities only locally or in a test environment. Do not send attack requests to production or to third-party services. Do not read or extract real users' data.
- Do not change code during the scan. Fixes happen in step 6.
- When this conversation wrote or changed code within the scan scope, dispatch steps 3 to 5 to an independent reviewer as the core [Independent Review](../software-engineering-guidelines/SKILL.md#independent-review) requires; the main conversation only checks the findings. The same applies to the re-check after fixing. A dispatched reviewer does the scan itself and does not dispatch further.

### 2. Fetch the latest lists

Following the rules in [references/list-sources.md](references/list-sources.md), fetch the latest edition of each applicable list from its entry page, and record each list's name, version, URL and fetch date. Handle and record lists that cannot be fetched according to that file's rules.

### 3. Inventory the attack surface

List the following, each with file locations. This inventory decides what the later steps check.

- Entry points: HTTP routes, GraphQL operations, RPC, WebSocket, CLI arguments, scheduled jobs, message queue consumers, webhooks, file imports, deep links.
- Trust boundaries: which inputs come from anonymous users, logged-in users, other tenants, third-party services, model output.
- Sensitive assets: credentials and keys, personal data, payments, admin functions, the file system, outbound requests, places that can execute commands.
- Where authentication and authorization are implemented, and which entry points do not pass through them.
- Technology stack: languages, frameworks, databases, dependencies and lockfiles, container and deployment configuration, CI/CD configuration.

### 4. Scan

Do all three tracks, then merge the results and remove duplicates.

**4a Tool scan.** Follow [references/scan-tools.md](references/scan-tools.md): determine the applicable tools from the files the project actually has, confirm one by one whether each is usable, and run every usable one. Do not install a tool that is not installed yourself; list it in the report's recommendations. Tool output is a lead; confirm every item against the code.

**4b List check.** Every item from the lists fetched in step 2 needs a conclusion: finding; checked with no finding (state which locations were examined); or not applicable (state the basis).

**4c Catalog check.** Take the attacker's side: assume every input is controlled by someone trying to break the system, and actively look for paths that bypass authentication, escalate privileges or abuse a flow, not only confirm that a protection exists. Go through the [vulnerability catalog](references/vulnerability-catalog.md) section by section. For each entry point from step 3, trace the input all the way to where it is used (query, command, file, response, outbound request) and confirm whether that section's protections are present along the way. Do not only search for dangerous function names: missing authorization, logic flaws and race conditions cannot be found by search; read the flow.

When the scope is large, you may dispatch subagents by section or by module, following **agent-delegation**. Each dispatch covers a set of files that does not overlap with the others, and its prompt states that files MUST NOT be modified and secret values MUST NOT be output. Reports include file line numbers and the basis for each judgment; the main agent adopts them only after checking them against the code.

### 5. Confirm and assign levels

Confirm each candidate finding before listing it:

1. State where the input enters, which code it passes through, and which line causes the problem.
2. State the conditions the attacker needs (anonymous, logged in, a specific role, victim interaction).
3. When it can be reproduced safely, reproduce it locally or in a test environment and keep the request and the result. When it cannot be reproduced, state the missing conditions and put it under "Needs investigation".

When no workable trigger path is found, it is not a vulnerability; it may go under "Hardening recommendations".

Levels are P0 to P3 from the core [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity). Criteria for security findings:

| Level | Criteria |
|---|---|
| P0 | Without logging in, or with only an ordinary account, an attacker can execute arbitrary code, obtain or tamper with large amounts of data, take over other people's accounts, or escalate to admin |
| P1 | An attacker can access or modify other users' data or bypass payment or a critical flow, or the required conditions are easy to meet |
| P2 | Requires specific conditions or victim interaction; impact is limited to a single user or to limited data |
| P3 | Very small impact, or requires several conditions that are not easily true at the same time |

For dependency vulnerabilities, confirm two more things: whether the project actually calls the affected functionality, and whether the CVE is on the CISA KEV list. Raise one level when it is on the list.

### 6. Fix

Handle findings in order from P0 to P3. Fix following **software-engineering-guidelines**:

- Fix the root cause, and search for other places with the same pattern and fix them together.
- Prefer the protections the framework or library provides. Do not write your own escaping, encryption or validation.
- Every fix needs the regression test required by the core [Regression Tests](../software-engineering-guidelines/SKILL.md#regression-tests).
- When a leaked secret is found, removing it from the code does not count as fixed. Ask the user to revoke and regenerate it at the service that issued it. Confirm cleanup of the history separately, and do not rewrite git history on your own.
- For a fix that changes existing behavior, interfaces or data, explain the impact first and get confirmation.

### 7. Verify and report

- Rerun the reproduction steps from step 5 and confirm the attack is blocked.
- Rerun the tools from step 4a and the project's full test suite, and confirm no new problems were introduced.
- Deliver the report per the Output Contract.

### diff mode

Follow steps 1 to 7, with these differences:

- **Scope (step 3)**: inventory only the entry points, data flows, configuration and dependencies the diff adds or changes. Trace each one beyond the diff: which existing code the input comes in through, and where the changed values flow to. When a change removes or bypasses an existing protection (authentication, authorization, escaping, rate limiting), list it as a candidate finding.
- **Lists (step 2)**: reuse lists already fetched in this conversation. When none has been fetched, fetch the CWE Top 25, the OWASP Top 10, and the lists for the technologies the diff touches.
- **Scan (step 4)**: when dependencies or lockfiles change, audit added packages and packages whose version went up or down. Check every string the diff adds for secrets. Check only the catalog sections the diff touches; the other sections need not be listed.
- **Fix (step 6)**: do not fix by default; return the findings to the caller. Fix only when the user or the caller asks.
- **Angle**: when the task states that it is to be done from the attacker's point of view, actually work out an attack path for every entry point the diff adds or changes, then judge whether it works.
- **Report**: deliver only items 1 to 4 of the Output Contract, plus the files and catalog sections actually checked. When handed over by diff-review, return the findings and needs-investigation items unchanged, for it to merge.
- When the diff touches no input, authentication, authorization, files, outbound requests, secrets, cryptography, dependencies or deployment configuration, report "This diff has no security-relevant changes" with the basis for that judgment, and do not run the full workflow.

## Output Contract

The report contains, in order:

1. **Conclusion**: the number of findings at each level, the number fixed, and the highest level still open.
2. **Scope and basis**: the directories and services scanned; the lists used (name, version, URL, fetch date); the tools run and their versions; what was not fetched or not run, and why.
3. **Findings**: from P0 to P3, each in the format of the core [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity), plus the category (list item ID and CWE), the conditions the attacker needs, the fix and the verification result. Write secrets as the core [Secrets](../software-engineering-guidelines/SKILL.md#secrets) requires.
4. **Needs investigation**: `NEEDS INVESTIGATION` items in the same format.
5. **Hardening recommendations**: protections worth adding that do not constitute vulnerabilities, and scan tools recommended for installation.
6. **List checklist**: the conclusion for every item of every list, and whether each catalog section applies.

The report goes in the conversation, or in the pull request when the scan is for one. A finding that is not fixed now is recorded as the core's [Engineering Documents](../software-engineering-guidelines/SKILL.md#engineering-documents) sets, and the report is written to a dated file as the same section sets only when the user asks to keep it. Both put unfixed vulnerabilities into the repository: when the repository is public or its visibility is unknown, say so and get the user's confirmation before writing either.

## Quality Rules

- An item without a code location and a trigger path is not listed as a finding.
- "Checked, no finding" states the locations actually examined. Write "not checked" for anything not examined.
- List versions are those fetched in this scan. When the latest edition was not fetched, say so; do not write that the latest edition was checked.
- Do not take scan tool output as a conclusion as it stands, and do not declare the code safe because a tool reported nothing.
- A completed scan does not mean the system is secure. The report states what this scan did not cover, for example production configuration, third-party services, physical and personnel aspects.

## Common Mistakes

| Mistake | Correct approach |
|---|---|
| Searching only for keywords like `eval` and `exec` and calling it done | Trace the data flow from every entry point; authorization and logic problems require reading the flow |
| Using an old ranking from memory | Fetch the current edition from the entry page every time |
| Marking all of dozens of dependency audit results as P0 | Confirm for each one whether the project uses the affected functionality |
| Finding one instance and fixing only that one | Search for the same pattern and fix all of them at once |
| Treating a secret as fixed once it is deleted from the code | Ask the user to revoke and rotate it |
| Trying attack requests in production | Reproduce only locally or in a test environment |
| In diff mode, looking only at the lines in the diff | Trace sources and destinations beyond the diff; vulnerabilities are often at the boundary between the change and existing code |
| Not rerunning the reproduction steps after fixing | Every fix needs evidence that it fails before the fix and passes after it |

## Suggested Prompt

```text
Run a security scan on this project, fix the vulnerabilities you find, and verify after fixing.
Scan only the api/ directory, give me the report first, and do not change the code.
```
