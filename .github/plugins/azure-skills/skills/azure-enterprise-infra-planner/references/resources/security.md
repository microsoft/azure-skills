# Security Resources

| Resource | ARM Type | API Version | CAF Prefix | Naming Scope | Region |
|----------|----------|-------------|------------|--------------|--------|
| Key Vault | `Microsoft.KeyVault/vaults` | `2024-11-01` | `kv` | Global | Foundational |
| Managed Identity | `Microsoft.ManagedIdentity/userAssignedIdentities` | `2024-11-30` | `id` | Resource group | Foundational |

## Documentation

| Resource | Bicep Reference | Service Overview | Naming Rules | Additional |
|----------|----------------|------------------|--------------|------------|
| Key Vault | [2024-11-01](https://learn.microsoft.com/azure/templates/microsoft.keyvault/vaults?pivots=deployment-language-bicep) | [Key Vault overview](https://learn.microsoft.com/azure/key-vault/general/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftkeyvault) | [Soft-delete](https://learn.microsoft.com/azure/key-vault/general/soft-delete-overview) |
| Managed Identity | [2024-11-30](https://learn.microsoft.com/azure/templates/microsoft.managedidentity/userassignedidentities?pivots=deployment-language-bicep) | [Managed identities](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftmanagedidentity) | [Workload identity federation](https://learn.microsoft.com/entra/workload-id/workload-identity-federation) |
