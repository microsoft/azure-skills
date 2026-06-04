## Azure Storage Cost Optimization

Reference guide for identifying cost savings opportunities in Azure Storage accounts through tier analysis, lifecycle policies, and orphaned resource detection.

## Subscription Input Options

Accept any of these identifiers to identify subscriptions for analysis:

| Input Type | Example | Use Case |
|------------|---------|----------|
| **Subscription ID** | `a1b2c3d4-...` | Analyze specific subscription |
| **Subscription Name** | `Production-Environment` | User-friendly identifier |
| **Subscription Prefix** | `StorageTeam -` | Analyze all team subscriptions |
| **Tenant ID** | `tenant-guid` | Analyze entire organization |
| **"All my subscriptions"** | (keyword) | Scan all accessible subscriptions |

## Cost Optimization Rules

When analyzing each storage account, apply these prioritized rules:

| Priority | Rule | Detection Logic | Recommendation | Avg Savings |
|----------|------|----------------|----------------|-------------|
| 🔴 Critical | Orphaned Managed Disks (Compute) | Managed disks with `managedBy` empty (billed as storage) | Delete or snapshot and delete | $20-500/mo |
| 🔴 Critical | Premium in Dev | `sku.name` contains `Premium` AND `tags.environment in ['dev','test','staging']` | Downgrade to Standard | $50-400/mo |
| 🟠 High | No Lifecycle Policy | Blob service has no lifecycle management rules configured | Add tiering/deletion rules | $50-300/mo |
| 🟠 High | Hot-Only with Infrequent Access | >80% of blobs unaccessed for 30+ days AND all in Hot tier | Move to Cool or enable auto-tiering | $30-200/mo |
| 🟠 High | GRS in Non-Production | `sku.name` contains `GRS` or `GZRS` AND `tags.environment in ['dev','test']` | Downgrade to LRS or ZRS | $40-300/mo |
| 🟠 High | Classic Storage Accounts | `kind == 'Storage'` (classic/v1) | Upgrade to StorageV2 for tiering support | Variable |
| 🟡 Medium | Large Snapshots | Snapshot cost exceeds 20% of base blob cost | Review snapshot retention policy | $20-100/mo |
| 🟡 Medium | Soft Delete Retention >30 days | `deleteRetentionPolicy.days > 30` | Reduce to 7-14 days unless compliance requires it | $10-50/mo |
| 🟡 Medium | No Access Tier Set | Blobs using default Hot when Cool would suffice | Set explicit Cool or Cold tier | $20-100/mo |
| 🟡 Medium | Unused Containers | Containers with zero blobs or zero access for 90+ days | Delete or archive contents | $5-50/mo |
| 🟢 Low | Untagged Storage Account | Missing required tags (`environment`, `owner`, `costCenter`) | Apply tags for cost allocation | N/A |
| 🟢 Low | Old Storage Account | Age >365 days without review | Verify still needed | Variable |
| 🟢 Low | Version-Heavy Blobs | Blob versioning enabled with >50 versions per blob | Add version deletion lifecycle rule | $5-30/mo |

## Access Tier Decision Matrix

| Last Access | Data Size | Access Pattern | Recommended Tier |
|-------------|-----------|----------------|-----------------|
| <30 days | Any | Frequent reads/writes | Hot |
| 30-90 days | Any | Occasional reads | Cool |
| 90-180 days | Any | Rare reads, compliance | Cold |
| >180 days | Any | Archival, legal hold | Archive |

> **Note**: Archive tier has retrieval costs and rehydration delays (hours). Only use for data that rarely needs access.

## Lifecycle Policy Template

Recommend this baseline policy for accounts without lifecycle management:

```json
{
  "rules": [
    {
      "name": "move-to-cool-after-30-days",
      "type": "Lifecycle",
      "definition": {
        "actions": {
          "baseBlob": {
            "tierToCool": { "daysAfterLastAccessTimeGreaterThan": 30 }
          }
        },
        "filters": { "blobTypes": ["blockBlob"], "prefixMatch": [] }
      }
    },
    {
      "name": "move-to-archive-after-180-days",
      "type": "Lifecycle",
      "definition": {
        "actions": {
          "baseBlob": {
            "tierToArchive": { "daysAfterLastAccessTimeGreaterThan": 180 }
          }
        },
        "filters": { "blobTypes": ["blockBlob"], "prefixMatch": [] }
      }
    },
    {
      "name": "delete-old-snapshots",
      "type": "Lifecycle",
      "definition": {
        "actions": {
          "snapshot": {
            "delete": { "daysAfterCreationGreaterThan": 90 }
          }
        },
        "filters": { "blobTypes": ["blockBlob"] }
      }
    },
    {
      "name": "delete-old-versions",
      "type": "Lifecycle",
      "definition": {
        "actions": {
          "version": {
            "delete": { "daysAfterCreationGreaterThan": 90 }
          }
        },
        "filters": { "blobTypes": ["blockBlob"] }
      }
    }
  ]
}
```

> ⚠️ **Important**: Lifecycle policies that use `daysAfterLastAccessTimeGreaterThan` require **last access time tracking** to be enabled on the storage account. Verify with: `az storage account blob-service-properties show --account-name <name> --resource-group <rg> --query lastAccessTimeTrackingPolicy`

## Resource Graph Queries

**Find storage accounts without lifecycle policies:**

Use Azure CLI to check lifecycle policy presence (not queryable via Resource Graph):

```bash
az storage account management-policy show --account-name <name> --resource-group <rg>
```

**Find Premium storage accounts in non-production:**

```kql
Resources
| where type =~ 'microsoft.storage/storageaccounts'
| where sku.name contains 'Premium'
| where tags.environment in~ ('dev', 'test', 'staging', 'sandbox')
| project name, resourceGroup, sku=sku.name, tags
```

**Find GRS/GZRS accounts in dev/test (redundancy downgrade candidates):**

```kql
Resources
| where type =~ 'microsoft.storage/storageaccounts'
| where sku.name contains 'GRS' or sku.name contains 'GZRS'
| where tags.environment in~ ('dev', 'test', 'staging')
| project name, resourceGroup, sku=sku.name, location, tags
```

**Find classic (v1) storage accounts:**

```kql
Resources
| where type =~ 'microsoft.storage/storageaccounts'
| where kind =~ 'Storage'
| project name, resourceGroup, location, kind
```

**Find orphaned managed disks (unattached):**

```kql
Resources
| where type =~ 'microsoft.compute/disks'
| where isempty(managedBy)
| project name, resourceGroup, location, diskSizeGb=properties.diskSizeGB, sku=sku.name
```

## Report Templates

### Subscription-Level Summary
Include: subscription name/ID, total monthly storage cost, account count by SKU/tier, total data stored (TB), top issues found.

### Detailed Storage Account Analysis
Include: account name, resource group, SKU/redundancy, kind, monthly cost, capacity (GB), access tier distribution (%), lifecycle policy status, and optimization recommendations.

## Tools & Commands

**MCP Tool:** `azure__storage` with sub-commands for account and container operations

**Azure CLI:**
- `az storage account list --subscription <id>` - List accounts
- `az storage account show --name <name> --resource-group <rg>` - Get details
- `az storage account management-policy show --account-name <name> --resource-group <rg>` - Check lifecycle policy
- `az storage account blob-service-properties show --account-name <name> --resource-group <rg> --query lastAccessTimeTrackingPolicy` - Check access tracking
- `az monitor metrics list --resource <id> --metric UsedCapacity` - Capacity metrics
- `az monitor metrics list --resource <id> --metric Transactions --dimension ApiName` - Access patterns

## Pricing Quick Reference

Tiers ranked by storage cost (East US, LRS, approximate):
- **Hot**: $0.018/GB/mo (cheapest reads)
- **Cool**: $0.01/GB/mo (30-day minimum retention)
- **Cold**: $0.0036/GB/mo (90-day minimum)
- **Archive**: $0.002/GB/mo (180-day minimum, hours to rehydrate)

Always validate from [official pricing](https://azure.microsoft.com/pricing/details/storage/blobs/).

**Redundancy savings**: Downgrading from GRS to LRS saves ~50%. Dev/test rarely needs GRS/GZRS.
