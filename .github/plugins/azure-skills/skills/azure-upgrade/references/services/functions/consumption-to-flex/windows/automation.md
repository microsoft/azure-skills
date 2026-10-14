# Automation: Consumption to Flex Consumption Upgrade

> Azure CLI scripts to automate the upgrade from Windows Consumption plan to Flex Consumption plan.
>
> **Shell compatibility**: Scripts use a universal subset that runs unchanged in:
>
> - bash 5.x (Cloud Shell, WSL, macOS, Linux)
> - PowerShell 7.x on any OS
>
> Secret-handling steps provide separate Bash and PowerShell 7 blocks when the shells require different cleanup or quoting syntax. Step 4c uses `jq` for the Bash in-memory JSON transform and `ConvertFrom-Json` / `ConvertTo-Json` for PowerShell.
>
> Replace `<PLACEHOLDERS>` (e.g. `<APP_NAME>`, `<RESOURCE_GROUP>`) with literal values before running each command. Each `az` command is a single line for cross-shell safety; conditional steps are described in prose between code blocks.
>
> **Source docs**: [Windows migration guide](https://learn.microsoft.com/en-us/azure/azure-functions/migration/migrate-plan-consumption-to-flex?pivots=platform-windows)
>
> `az functionapp flex-migration` does not support Windows. All migration steps are performed using raw Azure CLI commands.
>
> ⚠️ **Source-app safety invariant**: All discovery and replication steps treat the source app as read-only. Before any command that changes the source app's settings, triggers, state, deployment, bindings, or existence, use `ask_user` to describe the exact command and impact and obtain explicit approval. Approval applies only to that specific action.
>
> ⚠️ **Workflow continuity**: After each step succeeds, immediately perform the next read-only preflight. If the next action requires approval, invoke `ask_user` in the same turn. Never stop after only announcing the next step and wait for the user to re-engage.
>
> 📍 **Progress reporting**: Create and maintain `<UPGRADE_DIR>/upgrade-status.md` using [Migration Progress](progress-tracking.md). Derive the current and total phases and executable steps from the workflow headings, then display the same `Phase <current> of <total> · <step> · <description> · <state>` banner before and after every step. Do not use percentages.

## Workflow Files

Load only the file for the current workflow unit. Complete it before loading the next file unless that file explicitly directs otherwise.

| Order | Workflow unit | Instructions |
|-------|---------------|--------------|
| 1 | Prerequisites, discovery, and compatibility assessment | [Discovery and Assessment](automation/discovery-and-assessment.md) |
| 2 | Source configuration and dependency inventory | [Configuration Inventory](automation/configuration-inventory.md) |
| 3 | Deployment package retrieval when local source is unavailable | [Deployment Package](automation/deployment-package.md) |
| 4 | Target naming, storage selection, creation, and optional identity-based storage | [App Creation](automation/app-creation.md) |
| 5 | Production-setting copy or defer decision and secure transfer | [App Settings](automation/app-settings.md) |
| 6 | Site configuration and managed identities | [Site and Identity Configuration](automation/site-and-identity.md) |
| 7 | Built-in authentication configuration or migration deferral | [Built-in Authentication](automation/built-in-authentication.md) |
| 8 | CORS, domains, and access restrictions | [Networking and Storage](automation/networking-and-storage.md) |
| 9 | Pre-deployment trigger safety, monitoring, and configuration verification | [Trigger Safety and Monitoring](automation/trigger-safety-and-monitoring.md) |
| 10 | Access-key inventory and preservation decision | [Access Key Strategy](automation/access-key-strategy.md) |
| 11 | Code deployment | [Code Deployment](automation/code-deployment.md) |
| 12 | Post-deployment access-key copy and verification | [Access Key Copy](automation/access-key-copy.md) |
| 13 | Post-upgrade validation and production cutover | [Validation and Cutover](automation/validation-and-cutover.md) |
| 14 | Outcome-gated cleanup and rollback | [Cleanup and Rollback](automation/cleanup-and-rollback.md) |

The headings inside these files remain the source of truth for stable step IDs and progress tracking. The table defines execution order; filenames describe responsibilities and do not encode ordering.