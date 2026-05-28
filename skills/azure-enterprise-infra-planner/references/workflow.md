# Workflow

## Mandatory Rules

- You must execute the seven phases in sequential order. Follow the instructions precisely as defined. Do not continue to the next phase until the current phase is complete.
- You must stop on all "gate" conditions and only continue when the conditions have been met.
- Destructive actions require explicit user confirmation.
- You must read each phase's reference file in full before executing it.
- Never assume knowledge and cut corners or skip research steps.

## Overview

Starting from Phase 1, execute all phases in sequential order. Do not advance to the next phase until the current phase is complete and all of its gate conditions have been met.

| Phase | Action | Reference | Key Gate |
|-------|--------|-----------|----------|
| 1 | Extract insights | [1-extract-insights.md](phases/1-extract-insights.md) | Insights written to `<project-root>/.azure/insights.json` |
| 2 | Research best practices | [2-research-best-practices.md](phases/2-research-best-practices.md) | All MCP tool calls complete and WAF guides summarized |
| 3 | Research resources | [3-research-resources.md](phases/3-research-resources.md) | All resources have ARM type, naming rules, and pairing constraints; user approves resource list |
| 4 | Generate plan | [4-generate-plan.md](phases/4-generate-plan.md) | Plan JSON written to disk |
| 5 | Verify plan | [5-verify.md](phases/5-verify.md) | All checks pass, user approves |
| 6 | Generate IaC | [6-generate-iac.md](phases/6-generate-iac.md) | All IaC files generated and saved to disk |
| 7 | Deploy to Azure | [7-deploy.md](phases/7-deploy.md) | User confirms destructive actions |

## Plan Status Lifecycle

`draft` → `approved` → `deployed`

- `draft` — set by Phase 4 when the plan is written.
- `approved` — set by Phase 5 only after the user explicitly approves. Required before Phase 6 and Phase 7.
- `deployed` — set by Phase 7 after a successful `az deployment ... create` or `terraform apply`.

## Outputs

| Artifact | Location |
|----------|----------|
| Insights | `<project-root>/.azure/insights.json` |
| Infrastructure Plan | `<project-root>/.azure/infrastructure-plan.json` |
| Bicep files | `<project-root>/infra/main.bicep`, `<project-root>/infra/modules/*.bicep` |
| Terraform files | `<project-root>/infra/main.tf`, `<project-root>/infra/modules/**/*.tf` |

Before writing any `.bicep` or `.tf` files in Phase 6:

1. Create the `infra/` directory at `<project-root>/infra/`.
2. Create `infra/modules/` for child modules.
3. Write `main.bicep` (or `main.tf`) inside `infra/`, not in the project root or `.azure/`.
