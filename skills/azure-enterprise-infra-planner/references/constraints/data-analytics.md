# Data (Analytics) Pairing Constraints

### Cosmos DB

| Paired With | Constraint |
|-------------|------------|
| **Multi-region writes** | `consistencyPolicy.defaultConsistencyLevel` cannot be `Strong` when `enableMultipleWriteLocations: true`. |
| **Strong consistency** | Strong consistency with regions >5000 miles apart is blocked by default (requires support ticket to enable). Strong and Bounded Staleness reads cost 2× RU/s compared to Session/Consistent Prefix/Eventual. |
| **Serverless** | Cannot combine `EnableServerless` capability with multi-region writes or analytical store. Serverless is single-region only — cannot add regions. No shared throughput databases. Cannot provision throughput (auto-managed; settings return error). Merge partitions not available for serverless accounts. |
| **Free tier** | Only one free-tier account per subscription. Cannot combine with multi-region writes. |
| **VNet** | Set `isVirtualNetworkFilterEnabled: true` and configure `virtualNetworkRules[]` with subnet IDs. Subnets need `Microsoft.AzureCosmosDB` service endpoint. |
| **Private Endpoint** | Set `publicNetworkAccess: 'Disabled'` when using private endpoints exclusively. One Private DNS Zone record per DNS name — multiple private endpoints in different regions need separate Private DNS Zones. |
| **Key Vault (CMK)** | Requires `keyVaultKeyUri` in encryption config. Key Vault must be in same region. |
| **Merge Partitions** | Not available for serverless or multi-region write accounts. Single-region provisioned throughput only. |

### Redis Cache

| Paired With | Constraint |
|-------------|------------|
| **VNet** | Only Premium SKU supports VNet injection via `subnetId`. Basic/Standard use firewall rules only. |
| **VNet + Private Endpoint** | VNet injection and private endpoint are mutually exclusive — cannot use both on the same cache. |
| **Private Endpoint** | Available for Basic, Standard, Premium, and Enterprise tiers. Set `publicNetworkAccess: 'Disabled'` when using private endpoints. Premium with clustering supports max 1 private link; non-clustered supports up to 100. |
| **Clustering** | Only Premium SKU supports `shardCount`. Basic and Standard are single-node/two-node only. |
| **Persistence** | Only Premium SKU supports RDB/AOF persistence. Requires a storage account for RDB exports. |
| **Geo-replication** | Only Premium SKU. Primary and secondary must be Premium with same shard count. Passive geo-replication with private endpoints requires unlinking geo-replication first, adding private link, then re-linking. |
| **Zones** | Zone redundancy requires Premium SKU with multiple replicas. |
| **Tier Scaling** | Cannot scale down tiers (Enterprise → lower, Premium → Standard/Basic, Standard → Basic). Cannot scale between Enterprise and Enterprise Flash, or from Basic/Standard/Premium to Enterprise/Flash — must create a new cache. |
| **Enterprise/Flash** | Firewall rules and `publicNetworkAccess` flag are not available on Enterprise/Enterprise Flash tiers. |
| **Azure Lighthouse** | Azure Lighthouse + VNet injection is not supported. Use private links instead. |

### Storage Account

| Paired With | Constraint |
|-------------|------------|
| **Azure Functions** | Must use `StorageV2` or `Storage` kind. `BlobStorage`, `BlockBlobStorage`, `FileStorage` not supported (missing Queue/Table). |
| **Functions (Consumption plan)** | Cannot use network-secured storage (VNet rules). Only Premium/Dedicated plans support VNet-restricted storage. |
| **Functions (zone-redundant)** | Must use ZRS SKU (`Standard_ZRS`). LRS/GRS not sufficient. |
| **VM Boot Diagnostics** | Cannot use Premium storage or ZRS. Use `Standard_LRS` or `Standard_GRS`. Managed boot diagnostics (no storage account required) is also available. |
| **CMK Encryption** | Key Vault must have `enableSoftDelete: true` AND `enablePurgeProtection: true`. |
| **CMK at creation** | Requires user-assigned managed identity (system-assigned only works for existing accounts). |
| **Geo-redundant failover** | Certain features (SFTP, NFS 3.0, etc.) block GRS/GZRS failover. |

### Data Factory

| Paired With | Constraint |
|-------------|------------|
| **Storage Account** | Linked service requires `Storage Blob Data Contributor` role on the storage account for the ADF managed identity. For ADLS Gen2, also requires `Storage Blob Data Reader` at minimum. |
| **Key Vault** | For CMK encryption, Key Vault must have `enableSoftDelete: true` and `enablePurgeProtection: true`. ADF managed identity needs `Key Vault Crypto Service Encryption User` role or equivalent access policy. |
| **Managed VNet** | When `managedVirtualNetworks` is configured, all outbound connections must use managed private endpoints (`factories/managedVirtualNetworks/managedPrivateEndpoints`). |
| **Private Endpoint** | When `publicNetworkAccess: 'Disabled'`, must create private endpoint to `dataFactory` sub-resource for studio access and pipeline connectivity. |
| **Purview** | Requires Microsoft Purview instance resource ID. ADF managed identity must have `Data Curator` role in Purview. |
| **Integration Runtime** | Self-hosted IR requires network line-of-sight to on-premises sources. Azure IR regional choice affects data residency. |

### Synapse Workspace

| Paired With | Constraint |
|-------------|------------|
| **ADLS Gen2 Storage Account** | **Required.** Storage account must have `isHnsEnabled: true` (hierarchical namespace / Data Lake Storage Gen2) and `kind: 'StorageV2'`. Synapse managed identity needs `Storage Blob Data Contributor` role on the storage account. |
| **Key Vault** | For CMK encryption, Key Vault must have `enableSoftDelete: true` and `enablePurgeProtection: true`. Synapse managed identity needs `Get`, `Unwrap Key`, and `Wrap Key` permissions. |
| **Managed VNet** | When `managedVirtualNetwork: 'default'`, all outbound connections require managed private endpoints. Set at creation time — cannot be changed after. |
| **Private Endpoint** | When `publicNetworkAccess: 'Disabled'`, create private endpoints for sub-resources: `Dev` (Studio), `Sql` (dedicated SQL), `SqlOnDemand` (serverless SQL). |
| **Purview** | Requires Microsoft Purview resource ID. Synapse managed identity needs appropriate Purview roles. |
| **VNet (compute subnet)** | `virtualNetworkProfile.computeSubnetId` must reference an existing subnet. The subnet must be delegated to `Microsoft.Synapse/workspaces` if required by the deployment model. |
