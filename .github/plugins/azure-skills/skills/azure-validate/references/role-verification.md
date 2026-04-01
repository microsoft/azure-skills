# Role Assignment Verification

Verify that all RBAC role assignments in the generated infrastructure are correct and sufficient before deployment. Incorrect or missing roles are a common cause of runtime failures.

## When to Verify

After build verification (step 4) and **before** recording proof (step 6). Role issues surface as cryptic auth errors during deployment — catching them here saves debugging time.

## Verification Checklist

Review every resource-to-identity relationship in the generated Bicep/Terraform:

| Check | How |
|-------|-----|
| **Every service identity has roles** | Each app with a managed identity must have at least one role assignment |
| **Roles match data operations** | Use service-specific **data-plane** roles for data access (see mapping table below); use generic Reader/Contributor/Owner only for management-plane operations |
| **Scope is least privilege** | Roles scoped to specific resources, not resource groups or subscriptions |
| **No missing roles** | Cross-check app code operations against assigned roles (see table below) |
| **Local dev identity has roles** | If testing locally, the user's identity needs equivalent roles via `az login` |

## Common Service-to-Role Mapping

| Service Operation | Required Role | Common Mistake |
|-------------------|---------------|----------------|
| Read blobs | Storage Blob Data Reader | Using generic Reader (no data access) |
| Read + write blobs | Storage Blob Data Contributor | Missing write permission |
| Generate SAS via user delegation | Storage Blob Delegator + Data Reader/Contributor | Forgetting Delegator role |
| Read Key Vault secrets | Key Vault Secrets User | Using Key Vault Reader (no secret access) |
| Read + write Cosmos DB | Cosmos DB Built-in Data Contributor | Using generic Contributor |
| Send Service Bus messages | Azure Service Bus Data Sender | Using generic Contributor |
| Read queues | Storage Queue Data Reader | Using Blob role for queues |

## How to Verify (Static Code Review)

Review the generated Bicep/Terraform files directly — do **not** query live Azure state here. For each role assignment resource in your infrastructure code:

1. Identify the **principal** (which managed identity)
2. Identify the **role** (which role definition)
3. Identify the **scope** (which target resource)
4. Cross-check against the app code to confirm the role grants the required data-plane access

> 💡 **Tip:** Search your Bicep for `Microsoft.Authorization/roleAssignments` or your Terraform for `azurerm_role_assignment` to find all role assignments.

> ⚠️ **Live role verification** (querying Azure for actually provisioned roles) is handled by **azure-deploy** step 8 as a post-deployment check. This step is a static code review only.

## Decision Tree

```
For each app identity in the generated infrastructure:
├── Has role assignments?
│   ├── No → Add required role assignments to Bicep/Terraform
│   └── Yes → Check each role:
│       ├── Role matches code operations? → ✅ OK
│       ├── Role too broad? → Narrow to least privilege
│       └── Role insufficient? → Upgrade or add missing role
│
For local testing:
├── User identity has equivalent roles?
│   ├── No → Grant roles via CLI or inform user
│   └── Yes → ✅ Ready for functional verification
```

> ⚠️ **Warning:** Generic roles like `Contributor` or `Reader` do **not** include data-plane access. For example, `Contributor` on a Storage Account cannot read blobs — you need `Storage Blob Data Contributor`. This is the most common RBAC mistake.

## Record in Plan

After role verification, update `.azure/plan.md`:

```markdown
## Role Assignment Verification
- Status: Verified / Issues Found
- Identities checked: <list of app identities>
- Roles confirmed: <list of role assignments>
- Issues: <any missing or incorrect roles fixed>
```
