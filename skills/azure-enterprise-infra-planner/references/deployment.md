# Deployment Execution

Execute infrastructure deployment after plan approval and IaC generation.

## Status Gate

Before executing any deployment command, verify:

```txt
meta.status === "approved"
```

If status is not `approved`, stop and inform the user. Do not manually change the status.

## Pre-Deployment Checklist

1. Plan approved — `meta.status` is `approved`
2. IaC generated — Bicep or Terraform files exist in `<project-root>/infra/`
3. Azure context confirmed — subscription and resource group selected
4. User confirmation — explicit "yes, deploy" from the user
5. Syntax validated — `az bicep build` or `terraform validate` passed

## Bicep Deployment

Scope selection: use resource-group scope when your template deploys into an existing resource group. Use subscription scope when your template creates resource groups or other subscription-level resources (policies, role assignments, etc.).

```bash
# Validate first (applies to both scopes)
az bicep build --file infra/main.bicep
```

Choose the command based on the `targetScope` set in `main.bicep` (see [bicep-generation.md](bicep-generation.md) Bicep Conventions):

| `targetScope` | When to use | Command |
|---|---|---|
| `resourceGroup` (default) | All resources in one resource group | `az deployment group create` |
| `subscription` | Resources span multiple resource groups, or includes subscription-level resources (policy, RBAC, resource group creation) | `az deployment sub create` |

### Resource Group Scope

```bash
# What-if preview
az deployment group create \
  --resource-group <resource-group-name> \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --what-if

# Deploy
az deployment group create \
  --resource-group <resource-group-name> \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --name <deployment-name>
```

PowerShell:
```powershell
az deployment group create `
  --resource-group <resource-group-name> `
  --template-file infra/main.bicep `
  --parameters infra/main.bicepparam `
  --name <deployment-name>
```

### Subscription Scope

```bash
# What-if preview
az deployment sub create \
  --location <location> \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --what-if

# Deploy
az deployment sub create \
  --location <location> \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --name <deployment-name>
```

PowerShell:
```powershell
az deployment sub create `
  --location <location> `
  --template-file infra/main.bicep `
  --parameters infra/main.bicepparam `
  --name <deployment-name>
```

## Terraform Deployment

```bash
cd infra

# Initialize
terraform init

# Preview changes
terraform plan -var-file=prod.tfvars -out=tfplan

# Apply (requires confirmation)
terraform apply tfplan
```

PowerShell:
```powershell
Set-Location infra
terraform init
terraform plan -var-file=prod.tfvars -out=tfplan
terraform apply tfplan
```

## Post-Deployment

After successful deployment:

1. Update status — set `meta.status` to `deployed` in `<project-root>/.azure/infrastructure-plan.json`
2. Verify resources — list resources in the target resource group using Azure CLI: `az resource list -g <resource-group-name> -o table`
3. Report to user — list deployed resources, endpoints, and any follow-up actions

## Error Handling

| Error | Action |
|-------|--------|
| Authentication failure | Run `az login` and retry |
| Quota exceeded | Check limits with `mcp_azure_mcp_quota`, select different SKU or region |
| Name conflict | Resource name already taken; append unique suffix or choose new name |
| Region unavailable | Service not available in chosen region; select alternative |
| Validation failure | Fix IaC syntax errors before retrying deployment |
