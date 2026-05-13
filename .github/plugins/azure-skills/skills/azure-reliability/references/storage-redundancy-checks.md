# Storage Redundancy Checks

## Overview

Storage accounts underpin Azure Functions, Container Apps (for host storage), and App Service. If compute is zone-redundant but storage is not, a zone failure can still cause downtime.

## Replication Types

| Type | Zone Redundancy | Region Redundancy | Description |
|---|---|---|---|
| LRS | ❌ None | ❌ None | 3 copies in one datacenter. No zone or region protection. |
| ZRS | ✅ Zone-redundant | ❌ None | 3 copies across 3 availability zones in one region. |
| GRS | ❌ None (LRS per region) | ✅ Region-redundant | LRS in primary + LRS in secondary region. Zone failure in primary = risk. |
| GZRS | ✅ Zone-redundant | ✅ Region-redundant | ZRS in primary region + LRS in secondary region. Best protection. |
| RA-GRS | ❌ None (LRS per region) | ✅ Region + read | Like GRS but secondary is readable. Still LRS within each region. |
| RA-GZRS | ✅ Zone-redundant | ✅ Region + read | GZRS + read access to secondary. Maximum redundancy. |

## Minimum Requirement

- If compute is zone-redundant → storage MUST be at least **ZRS** (not GRS — GRS uses LRS in each region and is NOT zone-redundant)
- For multi-region failover → storage should be **GZRS** (zone + region) or **GRS** (region only, accepts zone risk)

## Resource Graph Queries

> **⚠️ Output format:** Use `--query "data[]" -o json` (not `-o table`). `az graph query -o table` only renders summary columns and does not show projected fields.

### Find All Storage Accounts and Their Replication

```bash
az graph query -q "
Resources
| where type =~ 'microsoft.storage/storageaccounts'
| extend replication = tostring(sku.name)
| extend tier = tostring(sku.tier)
| project name, resourceGroup, location, replication, tier, kind
| order by replication asc
" --query "data[]" -o json
```

> **💡 No SKU specified?** If a storage account was deployed without an explicit `sku.name` (raw ARM/Bicep) or `skuName` (AVM module), Azure defaults to **`Standard_GRS`**. Treat any storage account showing `Standard_GRS` as potentially "defaulted" rather than intentionally chosen — check the IaC source to confirm and recommend setting it explicitly to `Standard_ZRS` or `Standard_GZRS`.

### Find Storage Accounts Using LRS (Not Zone Redundant)

```bash
az graph query -q "
Resources
| where type =~ 'microsoft.storage/storageaccounts'
| where sku.name =~ 'Standard_LRS' or sku.name =~ 'Premium_LRS'
| project name, resourceGroup, location, replication=sku.name
" --query "data[]" -o json
```

### Find Function App Host Storage Accounts

```bash
# List function apps and their storage connections
az graph query -q "
Resources
| where type =~ 'microsoft.web/sites'
| where kind contains 'functionapp'
| project name, resourceGroup, location
" --query "data[]" -o json

# Then for each function app, check its storage:
az functionapp config appsettings list \
  --name <app-name> \
  --resource-group <rg> \
  --query "[?name=='AzureWebJobsStorage'].value" -o tsv
```

### Cross-Reference: Zone-Redundant Compute with Non-ZRS Storage

This is a critical gap detection query — zone-redundant compute paired with LRS storage:

```bash
# Step 1: Find zone-redundant plans
az graph query -q "
Resources
| where type =~ 'microsoft.web/serverfarms'
| where tobool(properties.zoneRedundant) == true
| project planName=name, resourceGroup, location
" --query "data[]" -o json

# Step 2: Check if associated storage accounts are ZRS
# (Requires app-level inspection of AzureWebJobsStorage setting)
```

## Remediation

### Upgrade Storage from LRS to ZRS

```bash
# Check if live migration is available (not all regions/account types support it)
az storage account show \
  --name <account-name> \
  --resource-group <rg> \
  --query "{name:name, sku:sku.name, kind:kind, location:location}"

# Request live migration (Standard_LRS → Standard_ZRS)
az storage account update \
  --name <account-name> \
  --resource-group <rg> \
  --sku Standard_ZRS
```

⚠️ **Limitations:**
- Live migration from LRS to ZRS is only supported for Standard general-purpose v2 accounts
- Premium accounts and legacy account types require manual migration (create new ZRS account + copy data)
- Migration can take hours to days depending on data volume

### Upgrade Storage from LRS to GRS/GZRS

```bash
# Upgrade to GRS
az storage account update \
  --name <account-name> \
  --resource-group <rg> \
  --sku Standard_GRS

# Upgrade to GZRS (zone + region redundant)
az storage account update \
  --name <account-name> \
  --resource-group <rg> \
  --sku Standard_GZRS
```

## Reporting

For the reliability checklist, mark the **ZRS Storage** column per storage account:
- ✅ — SKU is `Standard_ZRS` or `Standard_GZRS`
- ❌ (LRS) — `Standard_LRS` (no zone redundancy)
- ❌ (GRS) — `Standard_GRS` or `Standard_RAGRS` (region-redundant but uses LRS in each region; still a zone-failure risk). Also flag this when no SKU is set in IaC at all — ARM/AVM defaults to `Standard_GRS`.

⚠️ **Key distinction:** GRS provides region redundancy but uses LRS in each region. If compute is zone-redundant but storage is GRS (not ZRS/GZRS), a zone failure can still impact storage availability.
