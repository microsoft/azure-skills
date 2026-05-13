# Configure Storage Redundancy

## Overview

Storage accounts must match or exceed the redundancy level of the compute they support. Zone-redundant compute requires at minimum ZRS storage.

## Upgrade Paths

| Current | Target | Method | Downtime |
|---|---|---|---|
| Standard_LRS → Standard_ZRS | ZRS | Live migration or manual | None (live) or planned (manual) |
| Standard_LRS → Standard_GRS | GRS | In-place update | None |
| Standard_LRS → Standard_GZRS | GZRS | In-place update | None |
| Premium_LRS → Premium_ZRS | ZRS | Manual migration only | Planned |

## In-Place Upgrade (LRS → GRS/GZRS)

GRS and GZRS upgrades can be done in-place immediately:

```bash
# Upgrade to GZRS (zone + region redundant — recommended)
az storage account update \
  --name <account-name> \
  --resource-group <rg> \
  --sku Standard_GZRS

# Upgrade to GRS (region redundant only — NOT zone redundant)
az storage account update \
  --name <account-name> \
  --resource-group <rg> \
  --sku Standard_GRS
```

## Live Migration (LRS → ZRS)

ZRS conversion uses the storage account migration API (not `--sku` update):

```bash
# Check if account supports live migration
# Requirements: Standard general-purpose v2, in a supported region
az storage account show \
  --name <account-name> \
  --resource-group <rg> \
  --query "{name:name, sku:sku.name, kind:kind}"

# Start live migration to ZRS
az storage account migration start \
  --account-name <account-name> \
  -g <rg> \
  --sku Standard_ZRS \
  --name default \
  --no-wait

# Monitor migration status (can take hours to days)
az storage account migration show \
  --account-name <account-name> \
  -g <rg> \
  --migration-name default \
  --query "migrationStatus"
```

> **⛔ HARD GATE: Do NOT proceed to enable zone-redundant compute until migration status is `Succeeded` and `az storage account show --query sku.name` returns `Standard_ZRS`.**

⚠️ **Live migration limitations:**
- Only supported for **Standard general-purpose v2** accounts
- Premium storage accounts require manual migration
- BlobStorage and Storage (classic) kinds require manual migration
- Migration can take hours to days depending on data volume
- Account remains accessible during migration

## Manual Migration (When Live Migration Not Available)

For Premium_LRS or unsupported account types:

```bash
# 1. Create new ZRS storage account
az storage account create \
  --name <new-account-name> \
  --resource-group <rg> \
  --location <location> \
  --sku Standard_ZRS \
  --kind StorageV2
```

### For Function Apps (special handling required)

Function App host storage uses blobs, queues, tables, and potentially files. A simple blob-only copy is NOT sufficient.

**⛔ Full Function App storage migration workflow:**

```bash
# 1. Stop the function app to quiesce triggers and drain orchestrations
az functionapp stop --name <app-name> --resource-group <rg>

# 2. If using Durable Functions, wait for all orchestrations to complete
#    or terminate them before proceeding

# 3. Copy ALL storage services (blobs, queues, tables) using AzCopy
#    Authenticate first:
azcopy login

#    Copy blobs:
azcopy copy \
  "https://<old-account>.blob.core.windows.net/*" \
  "https://<new-account>.blob.core.windows.net/" \
  --recursive

#    Note: AzCopy does not support table/queue copy directly.
#    Use Azure Data Factory or Storage Explorer for tables/queues if needed.

# 4. Get new storage connection string
az storage account show-connection-string \
  --name <new-account-name> \
  --resource-group <rg> \
  --query connectionString -o tsv

# 5. Update app settings to point to new storage
az functionapp config appsettings set \
  --name <app-name> \
  --resource-group <rg> \
  --settings "AzureWebJobsStorage=<new-connection-string>"

# 6. Start the function app
az functionapp start --name <app-name> --resource-group <rg>

# 7. Verify app works — check logs, test triggers
az functionapp show --name <app-name> --resource-group <rg> --query "state"

# 8. Only delete old storage after confirming everything works
```

⚠️ **Warn user:** This involves app downtime. For zero-downtime migration, use live migration (Standard_ZRS) instead.

### For non-Function App workloads (simpler)

```bash
# Copy blobs
azcopy login
azcopy copy \
  "https://<old-account>.blob.core.windows.net/*" \
  "https://<new-account>.blob.core.windows.net/" \
  --recursive

# Update app connection strings as needed
# Delete old account after verification
```

## Function App Storage Considerations

Function Apps have a host storage account used for:
- Function code storage
- Timer trigger leases
- Event Hub checkpoints
- Durable Functions state

**Critical:** When upgrading Function App storage:
- The `AzureWebJobsStorage` connection string must point to the upgraded/new account
- If using a separate deployment storage account, upgrade that too
- Durable Functions state is stored in the host storage — ensure no active orchestrations during manual migration

```bash
# Check current storage connection
az functionapp config appsettings list \
  --name <app-name> \
  --resource-group <rg> \
  --query "[?name=='AzureWebJobsStorage'].value" -o tsv
```

## Verification

```bash
az graph query -q "
Resources
| where resourceGroup =~ '<rg>'
| where type =~ 'microsoft.storage/storageaccounts'
| project name, replication=sku.name, kind
" -o table
```

Expected: All accounts show `Standard_ZRS`, `Standard_GZRS`, or `Premium_ZRS`.
