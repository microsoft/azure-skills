# Security Pairing Constraints

### Key Vault

| Paired With | Constraint |
|-------------|------------|
| **Storage Account (CMK)** | Must have `enableSoftDelete: true` AND `enablePurgeProtection: true`. |
| **Storage Account (CMK at creation)** | Storage must use user-assigned managed identity — system-assigned only works for existing accounts. |
| **SQL Server (TDE)** | Must enable `enablePurgeProtection`. Key Vault and SQL Server must be in the same Azure AD tenant. |
| **AKS (secrets)** | Use `enableRbacAuthorization: true` with Azure RBAC for secrets access. AKS needs `azureKeyvaultSecretsProvider` addon. |
| **Disk Encryption** | Must set `enabledForDiskEncryption: true`. Premium SKU required for HSM-protected keys. |
| **Private Endpoint** | Set `publicNetworkAccess: 'Disabled'` and `networkAcls.defaultAction: 'Deny'` when using private endpoints. |
| **CMK Firewall** | When any Azure service uses CMK from Key Vault, the Key Vault firewall must enable "Allow trusted Microsoft services to bypass this firewall" — unless using private endpoints to Key Vault. |
| **CMK Key Type** | Key must be RSA or RSA-HSM, 2048/3072/4096-bit. Other key types are not supported for customer-managed keys. |
| **CMK Cross-Tenant** | Key Vault and consuming service must be in the same Azure AD tenant. Cross-tenant CMK requires separate configuration. |

### Managed Identity

| Paired With | Constraint |
|-------------|------------|
| **Any Resource (identity assignment)** | Reference the identity resource ID in the resource's `identity.userAssignedIdentities` object as `{ '${managedIdentity.id}': {} }`. |
| **Key Vault (CMK)** | Storage accounts using CMK at creation require a user-assigned identity — system-assigned only works for existing accounts. |
| **Container Registry (ACR pull)** | Assign `AcrPull` role to the identity's `principalId`. Reference the identity in the pulling resource (AKS, Container App, etc.). |
| **AKS (workload identity)** | Create a federated identity credential on the managed identity. Map it to a Kubernetes service account via OIDC issuer. |
| **Role Assignments** | Use `properties.principalId` with `principalType: 'ServicePrincipal'` in `Microsoft.Authorization/roleAssignments`. |
| **Function App / App Service** | Set `identity.type` to `'UserAssigned'` and reference the identity resource ID. Use for Key Vault references, storage access, etc. |
