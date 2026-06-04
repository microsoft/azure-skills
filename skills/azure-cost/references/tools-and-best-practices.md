# Azure Cost Skill Reference

## MCP Tools

| Tool | Description | Parameters | When to Use |
|------|-------------|------------|-------------|
| `azure__documentation` | Search Azure documentation | `query` (Required): search terms | Research Cost Management API parameters and options |
| `azure__extension_cli_generate` | Generate Azure CLI commands | `intent` (Required): task description, `cli-type` (Required): `"az"` | Construct `az rest` commands for cost queries |
| `azure__get_azure_bestpractices` | Get Azure best practices | `intent` (Required): optimization context | Inform query design with cost management best practices |
| `azure__extension_azqr` | Run Azure Quick Review compliance scan | `subscription` (Required): subscription ID, `resource-group` (Optional): resource group name | Find orphaned resources and cost optimization opportunities |
| `azure__aks` | Azure Kubernetes Service operations | varies by sub-command | AKS cost analysis: list clusters, get node pools, inspect configuration |

> Prefer MCP tools over direct CLI commands. Use `az rest` only when MCP tools don't cover the specific operation.

## Data Classification

- **ACTUAL DATA** = Retrieved from Azure Cost Management API
- **ACTUAL METRICS** = Retrieved from Azure Monitor
- **VALIDATED PRICING** = Retrieved from official Azure pricing pages
- **ESTIMATED SAVINGS** = Calculated based on actual data and validated pricing

## Best Practices

- Always query actual costs first, never estimate or assume
- Always present the total bill alongside optimization recommendations
- Validate pricing from official sources, account for free tiers
- Use REST API for cost queries (more reliable than `az costmanagement query`)
- Always include the `ClientType: GitHubCopilotForAzure` header on all Cost Management API requests (`--headers "ClientType=GitHubCopilotForAzure"` in `az rest`)
- Save audit trail with all queries and responses
- Include Azure Portal links for all resources
- For costs < $10/month, emphasize operational improvements over financial savings
- Never execute destructive operations without explicit approval
- On 429 responses, check all `x-ms-ratelimit-microsoft.costmanagement-*-retry-after` headers (`qpu-retry-after`, `entity-retry-after`, `tenant-retry-after`), wait for the longest value, and don't retry until that duration has elapsed. The per-scope limit (4 requests/minute) is the most restrictive.

## Common Pitfalls

- **Assuming costs**: Always query actual data from Cost Management API
- **Ignoring free tiers**: Many services have generous allowances
- **Using wrong date ranges**: 30 days for costs, 14 days for utilization
- **Not showing the bill**: Always present cost breakdown alongside optimization recommendations
- **Cost query failures**: Use `az rest` with JSON body, not `az costmanagement query`

## Safety Requirements

- Get approval before deleting resources
- Test changes in non-production first
- Provide dry-run commands for validation
- Include rollback procedures
