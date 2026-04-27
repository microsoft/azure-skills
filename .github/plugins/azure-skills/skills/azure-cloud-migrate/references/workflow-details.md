# Workflow Details

## Status Tracking

Maintain a `migration-status.md` file in the output directory (`<workspace-root-basename>-azure/`):

```markdown
# Migration Status
| Phase | Status | Notes |
|-------|--------|-------|
| Assessment | ⬜ Not Started | |
| Code Migration | ⬜ Not Started | |
```

Update status: ⬜ Not Started → 🔄 In Progress → ✅ Complete → ❌ Failed

## User Progress Updates

During long-running operations (Azure deployments, image pushes, environment provisioning), **proactively report progress** so the user is never left waiting without feedback:

1. **Resource-level status table** — After submitting a deployment, poll `az resource list` or `az deployment operation group list` and present a status table:
   ```
   | Resource | Status |
   |----------|--------|
   | VNet     | ✅ Created |
   | ACR      | ✅ Created |
   | Container Apps Env | 🔄 Provisioning |
   | order-service | ⬜ Waiting |
   ```
2. **Explain what's slow** — If a resource takes >2 minutes (e.g., Container Apps Environment with VNet), tell the user *why* ("VNet integration provisions internal load balancers and DNS — this typically takes 3-5 min").
3. **Don't go silent** — If a single `az deployment group create` covers all resources, poll `az resource list -g <rg>` periodically and update the user on newly created resources.
4. **Announce each phase transition** — When moving between skill phases (assess → migrate → deploy → validate), clearly tell the user what just completed and what's next.

## Error Handling

| Error | Cause | Remediation |
|-------|-------|-------------|
| Unsupported runtime | Source runtime not available in target Azure service | Check target service's supported languages documentation |
| Missing service mapping | Source service has no direct Azure equivalent | Use closest Azure alternative, document in assessment |
| Code migration failure | Incompatible patterns or dependencies | Review scenario-specific guide in [lambda-to-functions.md](services/functions/lambda-to-functions.md) |
| `azd init` refuses non-empty directory | azd requires clean directory for template init | Use temp directory approach: init in empty dir, copy files back |

> For scenario-specific errors (e.g., Azure Functions binding issues, trigger configuration), see the error table in the corresponding scenario reference.
