---
name: azure-upgrade
description: "Assess and upgrade Azure workloads between plans, tiers, or SKUs within Azure. Generates assessment reports and automates upgrade steps. WHEN: upgrade Consumption to Flex Consumption, upgrade Azure Functions plan, migrate hosting plan, upgrade Functions SKU, move to Flex Consumption, upgrade Azure service tier, change hosting plan, upgrade function app plan, migrate App Service to Container Apps."
license: MIT
metadata:
  author: Microsoft
  version: "1.0.1"
---

# Azure Upgrade

> This skill handles **assessment and automated upgrades** of existing Azure workloads from one Azure service, hosting plan, or SKU to another — all within Azure. This includes plan/tier upgrades (e.g. Consumption → Flex Consumption), cross-service migrations (e.g. App Service → Container Apps), and SKU changes. This is NOT for cross-cloud migration — use `azure-cloud-migrate` for that.

## Triggers

| User Intent | Example Prompts |
|-------------|-----------------|
| Upgrade Azure Functions plan | "Upgrade my function app from Consumption to Flex Consumption" |
| Change hosting tier | "Move my function app to a better plan" |
| Assess upgrade readiness | "Is my function app ready for Flex Consumption?" |
| Automate plan migration | "Automate the steps to upgrade my Functions plan" |

## Rules

1. Follow phases sequentially — do not skip
2. Generate an assessment before any upgrade operations
3. Load the scenario reference and follow its rules
4. Use `mcp_azure_mcp_get_azure_bestpractices` and `mcp_azure_mcp_documentation` MCP tools
5. Destructive actions require `ask_user` — [global-rules](references/global-rules.md)
6. Always confirm the target plan/SKU with the user before proceeding
7. Never delete or stop the original app without explicit user confirmation
8. All automation scripts must be idempotent and resumable

## Upgrade Scenarios

| Source | Target | Reference |
|--------|--------|-----------|
| Azure Functions Consumption Plan | Azure Functions Flex Consumption Plan | [consumption-to-flex.md](references/services/functions/consumption-to-flex.md) |

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
2. **Assess** — Analyze existing app for upgrade readiness → load scenario reference (e.g., [consumption-to-flex.md](references/services/functions/consumption-to-flex.md))
3. **Pre-migrate** — Collect settings, identities, configs from the existing app
4. **Upgrade** — Execute the automated upgrade steps (create new resources, migrate settings, deploy code)
5. **Validate** — Hit the function app default URL to confirm the app is reachable, then verify endpoints and monitoring
6. **Ask User** — "Upgrade complete. Would you like to verify performance, clean up the old app, or update your IaC?"
7. **Hand off** to `azure-validate` for deep validation or `azure-deploy` for CI/CD setup

Track progress in `upgrade-status.md` inside the workspace root.

## References

- [Global Rules](references/global-rules.md)
- [Workflow Details](references/workflow-details.md)
- **Functions**
  - [Consumption to Flex Consumption](references/services/functions/consumption-to-flex.md)
  - [Assessment](references/services/functions/assessment.md)
  - [Automation Scripts](references/services/functions/automation.md)

## Next

After upgrade is validated, hand off to:
- `azure-validate` — for thorough post-upgrade validation
- `azure-deploy` — if the user wants to set up CI/CD for the new app
