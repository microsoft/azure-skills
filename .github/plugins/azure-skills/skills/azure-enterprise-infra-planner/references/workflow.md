# Workflow

## Mandatory Rules

- You must execute the seven phases in sequential order. Follow the instructions precisely as defined. Do not continue to the next phase until the current phase is complete.
- You must stop on all "gate" conditions and only continue when the conditions have been met.
- Destructive actions require explicit user confirmation.
- **Confirmation gate vs. answer-first.** Always present a plain-language summary of your understanding plus an explicit "confirm before I proceed" checkpoint *before deploying* (Phase 7). In referenced mode you still generate the plan and IaC in the same turn (answer-first) — the gate governs *deployment*, not whether you produce the artifacts. Never end a turn with only a question, and never deploy without an explicit, risk-acknowledged go-ahead.
- **Never claim a gate passed without proof.** When a phase gate depends on a command (validation, security scan), run it and show its actual output/exit status; do not assert success from memory.
- You must read each phase's reference file in full before executing it.
- Never assume knowledge and cut corners or skip research steps.

## Overview

Starting from Phase 1, execute all phases in sequential order. Do not advance to the next phase until the current phase is complete and all of its gate conditions have been met.

## Phase 6 — hardened generation gate (apply inline)

The detailed generation reference files may not be loaded in every environment, so the Phase 6 gate is restated here and is mandatory. After generating the IaC, and **before** offering it or advancing to deploy:

1. **Secure-by-default.** Every resource: private endpoints + public network access disabled on data/PaaS services; managed identity + RBAC (never keys/connection strings); no secrets in code; storage shared-key access disabled; Key Vault soft-delete + purge protection; AKS managed identity with local accounts disabled; TLS 1.2 minimum.
2. **Validate + security-scan, fix until clean.** Bicep: `az bicep build --file infra/main.bicep`. Terraform: `terraform init -backend=false` then `terraform validate`. Then `checkov -d infra/`. Fix in-place and re-run until every command passes. **Paste the actual command output / exit status into your response** — never claim the gate passed without showing it. If a tool is genuinely unavailable, say so and self-review against the secure-by-default list.
3. **Completion self-check.** End Phase 6 with a checklist, each line marked pass/fail: validation clean (output shown); `checkov` no unresolved high/critical; secure-by-default applied; referenced resources wired and none recreated (referenced mode); files under `infra/` with original sources untouched.


> **Referenced workload?** If the user supplies something existing to reference or integrate with — a live Azure resource/resource group/subscription, a Bicep/Terraform/ARM file or infra plan, or a general doc of requirements/context — also read [referenced-workload.md](referenced-workload.md) and apply it alongside these phases. If not, run greenfield exactly as below.

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



