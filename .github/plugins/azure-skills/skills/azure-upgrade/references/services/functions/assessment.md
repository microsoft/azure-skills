# Assessment: Functions Plan Upgrade

Generate an upgrade assessment report before any changes to Azure resources.

## Prerequisites

- User has an existing Azure Functions app on a Consumption or other plan
- User has Azure CLI v2.77.0+ installed
- User has Owner or Contributor role in the target resource group
- The `resource-graph` extension is installed (`az extension add --name resource-graph`)

## Assessment Steps

1. **Identify Source App** — Confirm the function app name, resource group, region, and current hosting plan
2. **Check Region Compatibility** — Verify the target plan is available in the app's region
3. **Verify Language Stack** — Confirm the app's runtime is supported on the target plan
4. **Verify Stack Version** — Confirm the runtime version is supported on the target plan in the region
5. **Check Deployment Slots** — Determine if slots are in use (Flex Consumption doesn't support slots)
6. **Check Certificates** — Determine if TLS/SSL certificates are in use (not yet supported in Flex Consumption)
7. **Check Blob Triggers** — Verify blob triggers use EventGrid source (container polling not supported in Flex Consumption)
8. **Assess Dependencies** — Review upstream and downstream service dependencies and plan mitigation strategies
9. **Generate Report** — Create `upgrade-assessment-report.md`

## Assessment Report Format

> ⚠️ **MANDATORY**: Use these exact section headings in every assessment report. Do NOT rename, reorder, or omit sections.

The report MUST be saved as `upgrade-assessment-report.md` in the workspace root.

```markdown
# Upgrade Assessment Report

## 1. Executive Summary

| Property | Value |
|----------|-------|
| **App Name** | <app-name> |
| **Resource Group** | <resource-group> |
| **Current Plan** | <current-plan (e.g., Consumption / Y1 Dynamic)> |
| **Target Plan** | <target-plan (e.g., Flex Consumption / FC1)> |
| **Region** | <region> |
| **Runtime** | <runtime and version> |
| **OS** | <Linux / Windows> |
| **Upgrade Readiness** | <Ready / Needs Attention / Blocked> |
| **Assessment Date** | <date> |

## 2. Compatibility Checks

| Check | Status | Details |
|-------|--------|---------|
| Region supported | ✅ / ❌ | |
| Language stack supported | ✅ / ❌ | |
| Stack version supported | ✅ / ❌ | |
| No deployment slots | ✅ / ⚠️ | |
| No TLS/SSL certificates | ✅ / ⚠️ | |
| Blob triggers use EventGrid | ✅ / ⚠️ / N/A | |
| .NET isolated (not in-process) | ✅ / ❌ / N/A | |

## 3. App Settings Inventory

| Setting | Value | Migrate? | Notes |
|---------|-------|----------|-------|
| | | Yes / No / Convert | |

## 4. Managed Identities

| Type | Principal ID | Roles | Action |
|------|-------------|-------|--------|
| System-assigned | | | Recreate in new app |
| User-assigned | | | Reassign to new app |

## 5. Application Configurations

| Configuration | Current Value | Migrate? | Notes |
|---------------|---------------|----------|-------|
| CORS settings | | | |
| Custom domains | | | |
| HTTP version | | | |
| HTTPS only | | | |
| TLS version | | | |
| Client certificates | | | |
| Access restrictions | | | |
| Built-in auth | | | |

## 6. Trigger & Binding Analysis

| Function | Trigger Type | Source | Migration Risk | Mitigation |
|----------|-------------|--------|----------------|------------|
| | | | Low / Medium / High | |

## 7. Dependent Services

| Service | Dependency Type | Migration Risk | Mitigation Strategy |
|---------|----------------|----------------|---------------------|
| | Upstream / Downstream | | |

## 8. Blockers & Warnings

### Blockers (must fix before upgrade)
- [ ] <any blocking issues>

### Warnings (should address but not blocking)
- [ ] <any non-blocking concerns>

## 9. Recommendations

1. **Plan**: <recommended target plan>
2. **Auth**: <switch to Managed Identity if using connection strings>
3. **Monitoring**: <Application Insights configuration>
4. **Scaling**: <recommended instance count and concurrency settings>

## 10. Next Steps

- [ ] Review and approve this assessment
- [ ] Address any blockers listed above
- [ ] Proceed to automated upgrade (Phase 3-4)
```

> 💡 **Tip:** Use `mcp_azure_mcp_get_azure_bestpractices` to get the latest recommendations for the target hosting plan.
