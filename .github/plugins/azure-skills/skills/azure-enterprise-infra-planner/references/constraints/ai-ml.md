# AI & ML Pairing Constraints

### AI Search

| Paired With | Constraint |
|-------------|------------|
| **Cognitive Services (AI Enrichment)** | For AI enrichment pipelines (skillsets), attach a Cognitive Services account. Must be `kind: 'CognitiveServices'` or `kind: 'AIServices'` and in the same region as the search service. |
| **Storage Account (Indexers)** | Indexer data sources support Blob, Table, and File storage. Storage must be accessible (same VNet or public). For managed identity access, assign `Storage Blob Data Reader` role. |
| **Cosmos DB (Indexers)** | Indexer data source for Cosmos DB. Requires connection string or managed identity with `Cosmos DB Account Reader Role`. |
| **SQL Database (Indexers)** | Indexer data source. Requires change tracking enabled on the source table. |
| **Private Endpoints** | When `publicNetworkAccess: 'Disabled'`, create shared private link resources for outbound connections to data sources. |
| **Managed Identity** | Assign system or user-assigned identity for secure connections to data sources. Use RBAC instead of connection strings. |
| **Semantic Search** | Requires `semanticSearch` property set to `free` or `standard`. Available on `basic` and above SKUs. |

### Cognitive Services

| Paired With | Constraint |
|-------------|------------|
| **Azure OpenAI Deployments** | When `kind: 'OpenAI'` or `kind: 'AIServices'`, create model deployments as child resource `accounts/deployments`. |
| **Microsoft Entra ID Auth** | Requires `customSubDomainName` to be set. Without it, only API key auth works. |
| **Private Endpoint** | Requires `customSubDomainName`. Set `publicNetworkAccess: 'Disabled'` and configure private DNS zone. |
| **Key Vault (CMK)** | When using customer-managed keys, Key Vault must have soft-delete and purge protection enabled. Set `encryption.keySource: 'Microsoft.KeyVault'`. |
| **Storage Account** | When using `userOwnedStorage`, the storage account must be in the same region. Required for certain features (e.g., batch translation). |
| **AI Foundry Hub** | When `kind: 'AIServices'` with `allowProjectManagement: true`, can manage Foundry projects as child resources (`accounts/projects`). |
| **VNet Integration** | Configure `networkAcls` with `defaultAction: 'Deny'` and add virtual network rules. Set `bypass: 'AzureServices'` to allow trusted Azure services. |

### ML Workspace

| Paired With | Constraint |
|-------------|------------|
| **Storage Account** | Must be linked via `properties.storageAccount`. Cannot change after creation. Use `StorageV2` kind with standard SKU. |
| **Key Vault** | Must be linked via `properties.keyVault`. Cannot change after creation. Requires soft-delete enabled. |
| **Application Insights** | Linked via `properties.applicationInsights`. Should use workspace-based App Insights (backed by Log Analytics). |
| **Container Registry** | Optional but recommended for custom environments. Linked via `properties.containerRegistry`. |
| **Hub workspace (kind=Project)** | Must set `properties.hubResourceId` to the parent Hub's ARM resource ID. The Project inherits the Hub's linked resources. |
| **VNet Integration** | When `managedNetwork.isolationMode` is `AllowOnlyApprovedOutbound`, must configure outbound rules for all dependent services. |
