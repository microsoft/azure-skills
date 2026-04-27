---
name: azure-cloud-migrate
description: "Assess and migrate cross-cloud workloads to Azure with migration reports and code conversion. Supports AWS Lambda→Functions, Kubernetes→Container Apps, Cloud Run→Container Apps. WHEN: migrate Lambda to Functions, AWS to Azure, Lambda assessment, convert serverless to Azure, readiness report, from AWS, from GCP, Cloud Run to Container Apps, Kubernetes to Container Apps, Kubernetes to ACA, GKE to Azure, EKS to Container Apps."
license: MIT
metadata:
  author: Microsoft
  version: "1.1.3"
---

# Azure Cloud Migrate

> This skill handles **assessment and code migration** of existing cloud workloads to Azure.

## Rules

1. Follow phases sequentially — do not skip
2. Generate assessment before any code migration
3. Load the scenario reference and follow its rules
4. Use `mcp_azure_mcp_get_azure_bestpractices` and `mcp_azure_mcp_documentation` MCP tools
5. Use the latest supported runtime for the target service
6. Destructive actions require `ask_user` — [global-rules](references/services/functions/global-rules.md)
7. **Report progress to user** — During long-running operations (deployments, image pushes), provide resource-level status updates so the user is never left waiting without feedback — see [workflow-details.md](references/workflow-details.md)
8. **Audit service discovery in app code** — Kubernetes DNS names (e.g., `http://order-service:3001`) do not resolve in Container Apps. During assessment, scan source code for hardcoded hostnames/ports in HTTP clients and flag them for env-var-driven URL injection

## Migration Scenarios

| Source | Target | Reference |
|--------|--------|-----------|
| AWS Lambda | Azure Functions | [lambda-to-functions.md](references/services/functions/lambda-to-functions.md) ([assessment](references/services/functions/assessment.md), [code-migration](references/services/functions/code-migration.md)) |
| Kubernetes (GKE/EKS/Self-hosted) | Azure Container Apps | [k8s-to-container-apps.md](references/services/container-apps/k8s-to-container-apps.md) |
| GCP Cloud Run | Azure Container Apps | [cloudrun-to-container-apps.md](references/services/container-apps/cloudrun-to-container-apps.md) |

> No matching scenario? Use `mcp_azure_mcp_documentation` and `mcp_azure_mcp_get_azure_bestpractices` tools.

## Output Directory

All output goes to `<workspace-root-basename>-azure/` at workspace root, where `<workspace-root-basename>` is the name of the top-level workspace directory itself (NOT a subdirectory within it). Never modify the source directory.

## Steps

1. **Create** `<workspace-root-basename>-azure/` at workspace root
2. **Assess** — Analyze source, map services, generate report using scenario-specific assessment guide
3. **Migrate** — Convert code/config using scenario-specific migration guide
4. **Ask User** — "Migration complete. Test locally or deploy to Azure?"
5. **Hand off** to azure-prepare for infrastructure, testing, and deployment

Track progress in `migration-status.md` — see [workflow-details.md](references/workflow-details.md).
