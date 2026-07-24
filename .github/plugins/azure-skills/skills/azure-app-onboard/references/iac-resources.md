# IaC Resources — Official Documentation & Tools

Look up when stuck after 3 tries, edge cases, or validating generated code against ground truth.

## Bicep

| Resource | URL | Use When |
|----------|-----|----------|
| Bicep Documentation | https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/ | Syntax, file structure, deployment scopes, install |
| Azure Resource Reference | https://learn.microsoft.com/en-us/azure/templates/ | Resource properties, API versions, schema per type |

## Terraform

| Resource | URL | Use When |
|----------|-----|----------|
| Terraform Registry — azurerm | https://registry.terraform.io/providers/hashicorp/azurerm/latest | Resource type properties, argument reference, import blocks |
| Terraform Registry — azapi | https://registry.terraform.io/providers/azure/azapi/latest | Preview resources not yet in azurerm; maps to ARM REST APIs |

## Validation Tools

| Tool | Format | Purpose |
|------|--------|---------|
| `bicep build` | Bicep | Syntax + schema validation |
| `az deployment group create --what-if` | Bicep | ARM-level dry run with change preview |
| `terraform validate` | Terraform | Syntax + schema validation |
| `terraform plan` | Terraform | Provider-level dry run |

## Deploy Troubleshooting

> ⛔ **Primary lookup path:** Call `mcp_azure_mcp_documentation` with the error message first. Use the table below as fallback when MCP is unavailable or returns no results.
>
> **On repeat failures (same error 2+ consecutive attempts):** `fetch_webpage` the matching URL below with the error message as query. Apply the documented fix — do not retry the same approach.

| Resource | URL | Use When |
|----------|-----|----------|
| Common ARM Deployment Errors | https://learn.microsoft.com/en-us/azure/azure-resource-manager/troubleshooting/common-deployment-errors | `InvalidTemplateDeployment`, `SkuNotAvailable`, `QuotaExceeded`, any ARM error code |
| App Service Troubleshooting | https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/ | Startup crashes, Kudu/Oryx build failures, health probe issues |
| App Service Zip Deploy Guide | https://learn.microsoft.com/en-us/azure/app-service/deploy-zip | Zip deploy, SCM_DO_BUILD_DURING_DEPLOYMENT, Kudu publish API |
| Container Apps Troubleshooting | https://learn.microsoft.com/en-us/azure/container-apps/troubleshooting | Revision failures, ingress errors, secret resolution, image pull failures |
| Quota Increase Portal | https://portal.azure.com/#blade/Microsoft_Azure_Capacity/QuotaMenuBlade/myQuotas | Direct link for quota increase requests |

> **Source:** Official Microsoft Learn, HashiCorp Developer, and Azure documentation.
