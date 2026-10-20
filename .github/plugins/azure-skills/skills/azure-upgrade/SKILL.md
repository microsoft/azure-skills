---
name: azure-upgrade
description: "Assess and upgrade Azure workloads between plans, tiers, or SKUs, or modernize Azure SDK dependencies in source code. WHEN: upgrade Consumption to Flex Consumption, upgrade Azure Functions plan, change hosting plan, function app SKU, migrate App Service to Container Apps, modernize legacy Azure Java SDKs (com.microsoft.azure to com.azure), migrate Azure Cache for Redis (ACR/ACRE) to Azure Managed Redis (AMR)."
license: MIT
compatibility: python3.10+
metadata:
  author: Microsoft
  version: "1.2.3"
---

# Azure Upgrade

> This skill handles **assessment and automated upgrades** of existing Azure workloads from one Azure service, hosting plan, or SKU to another — all within Azure. This includes plan/tier upgrades (e.g. Consumption → Flex Consumption), cross-service migrations (e.g. App Service → Container Apps), and SKU changes. It also covers **Azure SDK for Java source-code modernization** (e.g. legacy Java `com.microsoft.azure.*` → modern `com.azure.*`). This is NOT for cross-cloud migration — use `azure-cloud-migrate` for that.

## Triggers

| User Intent | Example Prompts |
|-------------|-----------------|
| Upgrade Azure Functions plan | "Upgrade my function app from Consumption to Flex Consumption" |
| Discover Functions upgrade candidates | "What Consumption Function Apps do I have that can be upgraded to Flex Consumption?" |
| Change hosting tier | "Move my function app to a better plan" |
| Assess upgrade readiness | "Is my function app ready for Flex Consumption?" |
| Automate plan migration | "Automate the steps to upgrade my Functions plan" |
| Modernize legacy Azure Java SDK | "Migrate legacy Azure SDKs for Java", "Upgrade legacy Azure Java SDK", "Migrate my Java project from com.microsoft.azure to com.azure" |
| Migrate Azure Cache for Redis (ACR/OSS) to Azure Managed Redis (AMR) | "Migrate my Redis cache to AMR", "ACR to AMR", "OSS to AMR", "Upgrade my Premium P2 cache to Managed Redis", "Pick an AMR SKU", "Convert my Redis IaC template to AMR" |
| Migrate Azure Cache for Redis Enterprise (ACRE) to Azure Managed Redis (AMR) | "Migrate my Enterprise_E10 cache to AMR", "ACRE to AMR", "Update my ACRE IaC template for AMR", "Migrate EnterpriseFlash to AMR", "Migrate my geo-replicated Enterprise Redis" |

## Rules

1. Follow phases in order. Skip or defer work only when the selected scenario explicitly permits it, and record the reason in the migration status.
2. Generate an assessment before any upgrade operations
3. Load the scenario reference and follow its rules
4. Use `mcp_azure_mcp_get_azure_bestpractices` and `mcp_azure_mcp_documentation` MCP tools
5. Destructive actions require `ask_user` — [global-rules](references/global-rules.md)
6. Always confirm the target plan/SKU with the user before proceeding
7. **Propose a name for any new resource** (default: `<source>-<target-suffix>`, e.g. `<source>-flex` for Flex Consumption migrations) and **announce the proposed name to the user before creating it** so they can override without a blocking prompt. Same pattern applies to other newly-created resources (storage accounts, App Insights, etc.) — see the scenario reference for service-specific defaults.
8. **Windows Consumption → Flex source-change gate**: treat the source app as read-only by default. Immediately before every command that would change its settings, triggers, state, deployment, bindings, or existence, use `ask_user` to describe the exact change and obtain explicit approval. Approval is action-specific and cannot be reused for later source changes.
9. Never delete or stop the original app without explicit user confirmation
10. **Keep approval-gated workflows moving**: after each completed step, immediately perform the next read-only preflight. If the next action requires approval, invoke `ask_user` in the same turn — never stop after merely announcing the next step and wait for the user to re-engage.
11. All automation scripts must be idempotent and resumable

## Upgrade Scenarios

| Source | Target | Reference |
|--------|--------|-----------|
| Azure Functions Consumption Plan (Linux) | Azure Functions Flex Consumption Plan | [workflow.md](references/services/functions/consumption-to-flex/linux/workflow.md) |
| Azure Functions Consumption Plan (Windows) | Azure Functions Flex Consumption Plan | [workflow.md](references/services/functions/consumption-to-flex/windows/workflow.md) |
| Legacy Azure Java SDK (`com.microsoft.azure.*`) | Modern Azure Java SDK (`com.azure.*`) | [languages/java/README.md](references/languages/java/README.md) |
| Azure Cache for Redis (ACR/OSS) Basic/Standard/Premium | Azure Managed Redis (AMR) | [services/redis/redis-to-amr.md](references/services/redis/redis-to-amr.md) |
| Azure Cache for Redis Enterprise (ACRE) / Enterprise Flash | Azure Managed Redis (AMR) | [services/redis/redis-to-amr.md](references/services/redis/redis-to-amr.md) |

> **Functions Consumption-to-Flex routing:** For a named app, inspect its Azure platform and load only the matching Linux or Windows workflow. For subscription-wide discovery, evaluate both platforms: use `az functionapp flex-migration list` for Linux and the Windows workflow's manual discovery and compatibility checks for Windows. Label Windows results as candidates until per-app code compatibility is assessed.

> SDK upgrade scenarios (e.g. Java legacy → modern) run a **source-code modernization flow** that is distinct from Azure service/plan/SKU upgrades: follow the scenario reference, **not** the Steps below.

> No matching scenario? Use `mcp_azure_mcp_documentation` and `mcp_azure_mcp_get_azure_bestpractices` tools to research the upgrade path.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `mcp_azure_mcp_get_azure_bestpractices` | Get Azure best practices for the target service |
| `mcp_azure_mcp_documentation` | Look up Azure documentation for upgrade scenarios |
| `mcp_azure_mcp_appservice` | Query App Service and Functions plan details |
| `mcp_azure_mcp_applicationinsights` | Verify monitoring configuration |

## Steps

1. **Identify** — Determine the source and target Azure plans/SKUs. Ask user to confirm.
2. **Assess** — Analyze existing app for upgrade readiness → load scenario reference (e.g., [workflow.md](references/services/functions/consumption-to-flex/linux/workflow.md))
3. **Pre-migrate** — Collect settings, identities, configs from the existing app
4. **Upgrade** — Execute the automated upgrade steps (create new resources, migrate settings, deploy code)
5. **Validate** — Use the checks defined by the selected scenario: verify target resource state, applicable HTTP endpoints and non-HTTP triggers, and monitoring. If access restrictions or unavailable test resources prevent execution, record validation as deferred — never relax security automatically or report functional success.
6. **Ask User** — Offer performance validation and IaC updates. Offer source cleanup only when the selected scenario confirms production cutover and all cleanup prerequisites are complete.
7. **Hand off** to `azure-validate` for deep validation or `azure-deploy` for CI/CD setup

Track progress in `<UPGRADE_DIR>/upgrade-status.md` — see [Artifact Output Policy](references/global-rules.md#artifact-output-policy) for path resolution.

## References

- [Global Rules](references/global-rules.md)
- [Workflow Details](references/workflow-details.md)
- **Functions**
  - Linux
    - [Consumption to Flex Consumption](references/services/functions/consumption-to-flex/linux/workflow.md)
    - [Assessment](references/services/functions/consumption-to-flex/linux/assessment.md)
    - [Automation Scripts](references/services/functions/consumption-to-flex/linux/automation.md)
  - Windows
    - [Consumption to Flex Consumption](references/services/functions/consumption-to-flex/windows/workflow.md)
    - [Assessment](references/services/functions/consumption-to-flex/windows/assessment.md)
    - [Automation Scripts](references/services/functions/consumption-to-flex/windows/automation.md)
- **Redis**
  - [Redis (ACR or ACRE) to AMR Migration](references/services/redis/redis-to-amr.md) — routes to dedicated [amr-migration-skill](https://github.com/AzureManagedRedis/amr-migration-skill) (ACR/OSS) or [acre-to-amr-migration-skill](https://github.com/AzureManagedRedis/acre-to-amr-migration-skill) (Enterprise)
- **Java SDK Migration Templates**
  - [Plan Template](references/languages/java/templates/PLAN_TEMPLATE.md)
  - [Progress Template](references/languages/java/templates/PROGRESS_TEMPLATE.md)
  - [Summary Template](references/languages/java/templates/SUMMARY_TEMPLATE.md)

## Next

After upgrade is validated, hand off to:
- `azure-validate` — for thorough post-upgrade validation
- `azure-deploy` — if the user wants to set up CI/CD for the new app
