# MCP and CLI Tools for Azure Local

Prefer Azure MCP tools for Azure control-plane discovery where they support the Azure Local resource type, then use generated Azure CLI/PowerShell commands when a documented operation requires command execution. Azure MCP does not currently expose a dedicated Azure Local tool namespace; treat support as partial through generic Azure, Azure Resource Graph, documentation, monitor/resource health, and Bicep schema surfaces.

## MCP tools

| Tool | Use |
| --- | --- |
| `mcp_azure_mcp_subscription_list` | Discover subscription scope. |
| `mcp_azure_mcp_group_list` | Discover resource groups. |
| `mcp_azure_mcp_extension_cli_generate` | Generate Azure CLI or Azure Resource Graph commands for Azure Local/Arc inventory and operations. |
| `mcp_azure_mcp_monitor` | Query logs/metrics when Azure Monitor or Log Analytics is configured. |
| `mcp_azure_mcp_resourcehealth` | Check resource health where supported. |
| `mcp_azure_mcp_documentation` | Retrieve current Microsoft Learn content. |
| `mcp_azure_mcp_bicepschema` | Inspect ARM/Bicep schemas for Azure Local resource types such as `Microsoft.AzureStackHCI/clusters` when authoring templates. |

Do not assume public Azure service-specific MCP tools are interchangeable with Azure Local. For example, public Azure VM and AKS tools may not cover Arc VMs or AKS on Azure Local; confirm the resource provider/type and use ARG, generated CLI, or documented PowerShell when the dedicated MCP tool does not match.

## Azure CLI patterns

Use Azure CLI for Azure control-plane operations:

```bash
az account show
az group list -o table
az graph query -q "Resources | where type =~ 'microsoft.azurestackhci/clusters' | project name, resourceGroup, location" -o table
az resource show --ids <resource-id>
az monitor activity-log list --resource-id <resource-id> --max-events 20
```

For Azure Local VM operations, use the Azure Local VM management docs to determine the required extension/CLI commands and parameters. Do not assume public Azure VM commands have identical behavior for Azure Local VMs enabled by Azure Arc.

## PowerShell patterns

Use PowerShell when Microsoft Learn specifies Azure Local lifecycle, update, or local cluster commands. Confirm the command is supported for the user's Azure Local version before execution.

Common categories:

- Azure Local update assessment, import, scheduling, and installation.
- Local evidence collection from an Azure Local machine.
- SDN management/troubleshooting when docs require local or administrative PowerShell modules.
- Upgrade readiness and post-upgrade validation.

## When local machine access is required

Ask the user to confirm direct administrative access to an Azure Local machine before local commands. Local access may be required for:

- OS installation or simplified machine provisioning.
- Local logs or evidence collection.
- Update/upgrade commands that must run on a system node.
- SDN certificate or infrastructure troubleshooting.
- Arc resource bridge local VM state checks.

## Command safety

- Generate commands with read-only flags first.
- Scope all commands to the subscription/resource group/resource ID.
- Use `--first`, `--query`, or projection for large Azure Resource Graph queries.
- Ask before update installation, resource deletion, VM power operations, network changes, or decommissioning.
- Never embed secrets in commands. Use Key Vault, environment variables, or interactive authentication where documented.
