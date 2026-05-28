# Phase 4: Generate Plan

Build `<project-root>/.azure/infrastructure-plan.json` using the schema in [schema.md](../schema.md). Set `meta.status` to `draft`.

Use the user requirements and the research gathered from previous phases to assist:

- Phase 1: insights from `<project-root>/.azure/insights.json` (existing environment, user-selected focus areas).
- Phase 2: clarified requirements, derived sub-goals (`inputs.subGoals`), and WAF summaries covering missing resources, property hardening, and architecture patterns.
- Phase 3: refined resource list, including ARM types, naming rules, and pairing constraints.

> Important: Write the plan to file progressively using inline edits - never hold the full plan in a single tool-call output.

## Gate
- The plan is fully written to file.
