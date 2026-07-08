# Specialized Technology Routing

**MANDATORY**: Before starting any planning, check the user's prompt for specialized technology keywords. If matched, invoke the corresponding skill FIRST — it has tested templates and optimized workflows for that technology.

## Prompt-Based Routing Table

> **⚠️ PRIORITY RULE**: Check rows **top to bottom**. The first match wins. **Python + App Service (code-only) is the highest priority** — route to `python-appservice-deploy` ONLY when the prompt is a code-deploy request **without** IaC or infra keywords (see Priority 1 qualifier below). If the prompt mentions **AWS Lambda migration or AWS Lambda**, invoke **azure-cloud-migrate** even if Azure Functions are also mentioned.

| Priority | User prompt mentions | Invoke skill FIRST | Then resume azure-prepare at |
|----------|---------------------|--------------------|-----------------------------|
| **1 (highest)** | Python + Azure App Service **AND NOT** any of: `Terraform`, `Bicep`, `IaC`, `VNet`, `private endpoint`, `Key Vault`, `Cosmos`, `Postgres`, `MySQL`, `SQL`, `Front Door`, `multi-environment`, `Lambda`, `migrate from AWS`, `migrate from GCP`, `Fargate`, `Cloud Run`, `ECS`, `EKS`, `GKE` (e.g., "deploy Python to App Service", "Flask on App Service", "Python web app on App Service") | **python-appservice-deploy** | This is a code-only deploy skill. Do not resume `azure-prepare`. If the prompt contains any IaC, infra, or cross-cloud migration keyword above, **skip this row** and continue to row 2+ (i.e., let `azure-cloud-migrate` handle Lambda/Fargate/Cloud Run migrations, or stay in `azure-prepare` for the full infrastructure path). |
| 2 | Lambda, AWS Lambda, migrate AWS, migrate GCP, Lambda to Functions, migrate from AWS, migrate from GCP | **azure-cloud-migrate** | Phase 1 Step 4 (Select Recipe) — azure-cloud-migrate does assessment + code conversion, then azure-prepare takes over for infrastructure, local testing, or deployment |
| 3 | Azure Functions, function app, serverless function, timer trigger, HTTP trigger, queue trigger, func new, func start | Stay in **azure-prepare** | Phase 1 Step 4 (Select Recipe) — prefer Azure Functions templates |
| 4 (lowest) | workflow, orchestration, multi-step, pipeline, fan-out/fan-in, saga, long-running process, durable, order processing | Stay in **azure-prepare** | Phase 1 Step 4 — select **durable** recipe. **MUST** load [durable.md](services/functions/durable.md), [DTS reference](services/durable-task-scheduler/README.md), and [DTS Bicep patterns](services/durable-task-scheduler/bicep.md). |

> ⚠️ This checks the user's **prompt text**, not just existing code. Essential for greenfield projects where there is no codebase to scan.

## Why This Step Exists

azure-prepare is the default entry point for all Azure app work. Some technologies have dedicated skills with:
- Pre-tested `azd` templates that avoid manual scaffolding errors
- Specialized configuration (BYOM model config)
- Optimized infrastructure patterns

Without this check, azure-prepare generates generic infrastructure that misses these optimizations.

> ⚠️ **Re-entry guard**: When azure-prepare is invoked as a **resume** from a specialized skill (e.g., `python-appservice-deploy` handing back for full-infra needs like VNet / Key Vault / DB provisioning), **skip this routing check** and proceed directly to Step 4. The specialized skill has already completed its work.

## Flow

```
User prompt → azure-prepare activated
  │
  ├─ Prompt mentions specialized tech?
  │   ├─ YES → Invoke specialized skill → Skill scaffolds + configures
  │   │         → Resume azure-prepare at Step 4 (recipe/infra/validate/deploy)
  │   └─ NO  → Continue normal azure-prepare workflow from Step 1
  │
  └─ Phase 1 Step 3 (Scan Codebase) also detects tech indicators in existing files
      → See [scan.md](scan.md) for file-based detection
```

## Complementary Checks

This prompt-based check complements — does not replace — existing file-based detection:
- **[scan.md](scan.md)** — Detects tech in dependency files (package.json, requirements.txt)
- **[analyze.md](analyze.md)** — Delegation table triggered by user mentions during planning
- **[research.md](research.md)** — Skill invocation during research phase

The prompt check catches **greenfield** scenarios where no code exists yet.
