# Consultation flow for changes to an existing API

The trigger condition is in "Changes to an existing API" in [SKILL.md](../SKILL.md).

- Changes include the name, signature, parameters, return value, errors and side effects of a function or method, and the name, structure or usage of a variable, field, struct or Enum. Being private, internal, small, or implemented by the main agent itself is not an exemption.
- Before modifying the affected skeleton, tests or implementation, first review the existing definitions, call sites, tests and documentation, prepare a first draft, the reasons for the change and the compatibility impact, then hand them to an independent model for consultation. The main agent's own reasoning does not count as consultation.

| Main agent environment | Consultation model |
| --- | --- |
| Claude | Fable 5.1 or later; when no qualifying Fable is available, Opus 5.5 or later |
| GPT | Astra |

Choose by the model family the main agent actually uses; do not guess from the CLI name. In any other model environment, first ask the user to name the consultation model. Use the model identifier and version the current tool actually provides; when an alias is not enough to prove the minimum version, verify first. Follow the execution rules of the host's built-in subagent or the external CLI. When the designated model cannot be used, only the alternative listed in the table may be used. When there is still no usable model, report the evidence, pause that interface change and ask the user to decide; other independent work may continue.

1. **Consult**: provide the existing code and usage examples, the first draft, the reasons for the change, constraints and the open decisions. Ask the consultant to check naming and usage, behavior differences, compatibility and alternatives, with the basis for each point and uncertainties marked. The consultation task MUST NOT modify any file.
2. **Revise the first draft**: the main agent checks the feedback against the original content, adopts suggestions that have a basis and revises the plan. Briefly state the reason for each important suggestion not adopted; do not repost the model's reply, and do not force changes to a reasonable first draft just to show it was revised.
3. **Hand to the user to decide**: present the revised plan together with the items that already needed the user's decision. Show the current state and the proposed change, a minimal usage example, the compatibility and migration impact, the recommended option and the main trade-offs. For a behavior change, compare the results before and after on the same input; listing function signatures alone is not enough. For the format, see [Interface change proposal examples](api-change-examples.md).
4. **Implement as decided**: after the user confirms the specific plan, return to the original implementation and verification flow. Do not ask again about parts already confirmed and unchanged. Open decisions added or changed after the consultation MUST be confirmed first. When a dispatch involves these interfaces, list the approved scope in the prompt. When a worker finds that another interface change is needed, it reports to the main agent first, and the main agent handles it under this section.
