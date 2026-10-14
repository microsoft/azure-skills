# Assessment: Functions Plan Upgrade

Generate an upgrade assessment report before any changes to Azure resources.

## Prerequisites

- User has an existing Azure Functions app on a Consumption or other plan running on Windows
- User has Azure CLI v2.77.0+ installed
- User has Owner or Contributor role in the target resource group
- The `resource-graph` extension is installed (`az extension add --name resource-graph`)

## Assessment Steps

1. **Identify Source App** — Confirm the function app name, resource group, region, and current hosting plan
2. **Check Region Compatibility** — Verify the target plan is available in the app's region
3. **Verify Language Stack** — Confirm the app's runtime is supported on the target plan
4. **Verify Stack Version** — Confirm the runtime version is supported on the target plan in the region
5. **Check Deployment Slots** — Determine if slots are in use (Flex Consumption doesn't support slots)
6. **Check Certificates** — Determine whether TLS/SSL certificates are used and plan for the documented site-scoped certificate model, limits, and Linux certificate-loading paths
7. **Check Blob Triggers** — Verify blob triggers use EventGrid source (container polling not supported in Flex Consumption)
8. **Scan Source for Windows Dependencies** — Recommended but skippable. Static-analyze source code or deployment package for Win32/COM/WMI/registry/cert-store usage, Windows-only packages, Windows-RID targeting, and shell-outs to Windows tools. See [dependency-scan.md](dependency-scan.md) for the procedure and severity rubric. Findings populate §11 of the report; `Blocker` findings advisorily flip §1 `Upgrade Readiness` to `Needs Attention` (never hard-blocks).
9. **Assess Dependencies** — Review upstream and downstream service dependencies and plan mitigation strategies
10. **Generate Report** — Create `<UPGRADE_DIR>/upgrade-assessment-report.md`

## Assessment Report Format

> ⚠️ **MANDATORY**: Use these exact section headings in every assessment report. Do NOT rename, reorder, or omit sections.

The report MUST be saved as `<UPGRADE_DIR>/upgrade-assessment-report.md`. See [Artifact Output Policy](../../../../global-rules.md#artifact-output-policy) for how `<UPGRADE_DIR>` resolves (default: `.azure-upgrade/<source-app-name>/`).

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
| **OS** | Windows |
| **Upgrade Readiness** | <Ready / Needs Attention / Blocked> |
| **Assessment Date** | <date> |

## 2. Compatibility Checks

| Check | Status | Details |
|-------|--------|---------|
| Region supported | ✅ / ❌ | |
| Language stack supported | ✅ / ❌ | |
| Stack version supported | ✅ / ❌ | |
| No deployment slots | ✅ / ⚠️ | |
| TLS/SSL certificates assessed | ✅ / ⚠️ / N/A | |
| Blob triggers use EventGrid | ✅ / ⚠️ / N/A | |
| .NET isolated (not in-process) | ✅ / ❌ / N/A | |
| Source code Windows dependency scan | ✅ / ⚠️ / ⏭ Skipped | See §11 |

## 3. App Settings Inventory

> Record setting names only. Never include app-setting values in the assessment.
> For surviving names containing `:`, mark **Migrate?** as `Convert` and record the Linux target name with `:` replaced by `__`. Note that .NET configuration maps `__` back to `:`.

| Setting | Migrate? | Notes |
|---------|----------|-------|
| | Yes / No / Convert | |

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
| TLS/SSL certificates | | | Re-add used certificates with the site-scoped certificate process |
| Explicit Azure Files mounts | | No | Catalog custom ID, account, share, type, and mount path; Windows Consumption doesn't support these mounts |
| Access restrictions | | | |
| Built-in auth | | Conditional | Configure and validate in Step 4f.auth, or record as deferred |
| Function access keys | | Conditional | Choose target-generated keys or preserve source host and HTTP-function keys; system and master keys aren't copied |

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

## 11. Source Code Windows Dependency Scan

| Property | Value |
|----------|-------|
| **Scan ran?** | Yes / No (skipped by user) |
| **Source scanned** | <local path / git URL / package from Step 3e> |
| **Language pattern set** | <FUNCTIONS_WORKER_RUNTIME value> |
| **Blockers** | <count> |
| **Likely issues** | <count> |
| **Manual review** | <count> |

### Findings

| Severity | Category | File | Line | Match | Remediation |
|----------|----------|------|------|-------|-------------|
| 🛑 / ⚠️ / ℹ️ | 1-8 | | | | |

> 📝 **Heuristic aid, not a guarantee.** The findings table reflects pattern matches only — uncommon Windows APIs, dynamically-loaded native libraries, transitive package dependencies, reflection-based calls, and runtime-generated code may not appear. The app owner is responsible for verifying no Windows dependencies remain.
>
> If `Scan ran? = No`, write a single line in place of the findings table: *"User declined the source code dependency scan. Migration proceeded without static analysis of Windows dependencies."*
>
> See [dependency-scan.md](dependency-scan.md) for the categories, severity rubric, and per-language patterns.
```

> 💡 **Tip:** Use `mcp_azure_mcp_get_azure_bestpractices` to get the latest recommendations for the target hosting plan.
