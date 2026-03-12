---
name: azure-quotas
description: "Check/manage Azure quotas and usage across providers. For deployment planning, capacity validation, region selection. WHEN: \"check quotas\", \"service limits\", \"current usage\", \"request quota increase\", \"quota exceeded\", \"validate capacity\", \"regional availability\", \"provisioning limits\", \"vCPU limit\", \"how many vCPUs available in my subscription\"."
license: MIT
metadata:
  author: Microsoft
  version: "1.0.5"
---

---

# Azure Quotas - Service Limits & Capacity Management

> **AUTHORITATIVE GUIDANCE** — Follow these instructions exactly for quota management and capacity validation.

## Overview

**What are Azure Quotas?**

Azure quotas (also called service limits) are the maximum number of resources you can deploy in a subscription. Quotas:
- Prevent accidental over-provisioning
- Ensure fair resource distribution across Azure
- Represent **available capacity** in each region
- Can be increased (adjustable quotas) or are fixed (non-adjustable)

**Key Concept:** **Quotas = Resource Availability**

If you don't have quota, you cannot deploy resources. Always check quotas when planning deployments or selecting regions.

## When to Use This Skill

Invoke this skill when:

- **Planning a new deployment** - Validate capacity before deployment
- **Selecting an Azure region** - Compare quota availability across regions
- **Troubleshooting quota exceeded errors** - Check current usage vs limits
- **Requesting quota increases** - Submit increase requests via CLI or Portal
- **Comparing regional capacity** - Find regions with available quota
- **Validating provisioning limits** - Ensure deployment won't exceed quotas

## Quick Reference

| **Property** | **Details** |
|--------------|-------------|
| **Primary Tool** | Azure CLI (`az quota`) - **USE THIS FIRST, ALWAYS** |
| **Extension Required** | `az extension add --name quota` (MUST install first) |
| **Key Commands** | `az quota list`, `az quota show`, `az quota usage list`, `az quota usage show` |
| **Complete CLI Reference** | [commands.md](./references/commands.md) |
| **Azure Portal** | [My quotas](https://portal.azure.com/#blade/Microsoft_Azure_Capacity/QuotaMenuBlade/myQuotas) - Use only as fallback |
| **REST API** | Microsoft.Quota provider - **Unreliable, do NOT use first** |
| **Required Permission** | Reader (view) or Quota Request Operator (manage) |

> **⚠️ CRITICAL: ALWAYS USE CLI FIRST**
>
> **Azure CLI (`az quota`) is the ONLY reliable method** for checking quotas. **Use CLI FIRST, always.**
>
> **DO NOT use REST API or Portal as your first approach.** They are unreliable and misleading.
>
> **Why you must use CLI first:**
> - REST API is unreliable and shows misleading results
> - REST API "No Limit" or "Unlimited" values **DO NOT mean unlimited capacity**
> - "No Limit" typically means the resource doesn't support quota API (not unlimited!)
> - CLI provides clear `BadRequest` errors when providers aren't supported
> - CLI has consistent output format and better error messages
> - Portal may show incomplete or cached data
>
> **Mandatory workflow:**
> 1. **FIRST:** Try `az quota list` / `az quota show` / `az quota usage show`
> 2. **If CLI returns `BadRequest`:** Then use [Azure service limits docs](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits)
> 3. **Never start with REST API or Portal** - only use as last resort
>
> **If you see "No Limit" in REST API/Portal:** This is NOT unlimited capacity. It means:
> - The quota API doesn't support that resource type, OR
> - The quota isn't enforced via the API, OR  
> - Service-specific limits still apply (check documentation)
>
> For complete CLI command reference and examples, see [commands.md](./references/commands.md).

## Quota Types

| **Type** | **Adjustability** | **Approval** | **Examples** |
|----------|-------------------|--------------|--------------|
| **Adjustable** | Can increase via Portal/CLI/API | Usually auto-approved | VM vCPUs, Public IPs, Storage accounts |
| **Non-adjustable** | Fixed limits | Cannot be changed | Subscription-wide hard limits |

**Important:** Requesting quota increases is **free**. You only pay for resources you actually use, not for quota allocation.

## Understanding Resource Name Mapping

**⚠️ CRITICAL:** There is **NO 1:1 mapping** between ARM resource types and quota resource names.

### Example Mappings

| ARM Resource Type | Quota Resource Name |
|-------------------|---------------------|
| `Microsoft.App/managedEnvironments` | `ManagedEnvironmentCount` |
| `Microsoft.Compute/virtualMachines` | `standardDSv3Family`, `cores`, `virtualMachines` |
| `Microsoft.Network/publicIPAddresses` | `PublicIPAddresses`, `IPv4StandardSkuPublicIpAddresses` |

### Discovery Workflow

**Never assume the quota resource name from the ARM type.** Always use this workflow:

1. **List all quotas** for the resource provider:
   ```bash
   az quota list --scope /subscriptions/<id>/providers/<ProviderNamespace>/locations/<region>
   ```

2. **Match by `localizedValue`** (human-readable description) to find the relevant quota

3. **Use the `name` field** (not ARM resource type) in subsequent commands:
   ```bash
   az quota show --resource-name ManagedEnvironmentCount --scope ...
   az quota usage show --resource-name ManagedEnvironmentCount --scope ...
   ```

> **📖 Detailed mapping examples and workflow:** See [commands.md - Understanding Resource Name Mapping](./references/commands.md#understanding-resource-name-mapping)

## Core Workflows

### Workflow 1: Check Quota for a Specific Resource

**Scenario:** Verify quota limit and current usage before deployment

```bash
# 1. Install quota extension (if not already installed)
az extension add --name quota

# 2. List all quotas for the provider to find the quota resource name
az quota list \
  --scope /subscriptions/<subscription-id>/providers/Microsoft.Compute/locations/eastus

# 3. Show quota limit for a specific resource
az quota show \
  --resource-name standardDSv3Family \
  --scope /subscriptions/<subscription-id>/providers/Microsoft.Compute/locations/eastus

# 4. Show current usage
az quota usage show \
  --resource-name standardDSv3Family \
  --scope /subscriptions/<subscription-id>/providers/Microsoft.Compute/locations/eastus
```

**Example Output Analysis:**
- Quota limit: 350 vCPUs
- Current usage: 50 vCPUs
- Available capacity: 300 vCPUs (350 - 50)

> **📖 See also:** [az quota show](./references/commands.md#az-quota-show), [az quota usage show](./references/commands.md#az-quota-usage-show)

### Workflow 2: Compare Quotas Across Regions

**Scenario:** Find the best region for deployment based on available capacity

```bash
# Define candidate regions
REGIONS=("eastus" "eastus2" "westus2" "centralus")
VM_FAMILY="standardDSv3Family"
SUBSCRIPTION_ID="<subscription-id>"

# Check quota availability across regions
for region in "${REGIONS[@]}"; do
  echo "=== Checking $region ==="
  
  # Get limit
  LIMIT=$(az quota show \
    --resource-name $VM_FAMILY \
    --scope "/subscriptions/$SUBSCRIPTION_ID/providers/Microsoft.Compute/locations/$region" \
    --query "properties.limit.value" -o tsv)
  
  # Get current usage
  USAGE=$(az quota usage show \
    --resource-name $VM_FAMILY \
    --scope "/subscriptions/$SUBSCRIPTION_ID/providers/Microsoft.Compute/locations/$region" \
    --query "properties.usages.value" -o tsv)
  
  # Calculate available
  AVAILABLE=$((LIMIT - USAGE))
  
  echo "Region: $region | Limit: $LIMIT | Usage: $USAGE | Available: $AVAILABLE"
done
```

> **📖 See also:** [Multi-region comparison scripts](./references/commands.md#multi-region-comparison) (Bash & PowerShell)

### Workflow 3: Request Quota Increase

**Scenario:** Current quota is insufficient for deployment

```bash
# Request increase for VM quota
az quota update \
  --resource-name standardDSv3Family \
  --scope /subscriptions/<subscription-id>/providers/Microsoft.Compute/locations/eastus \
  --limit-object value=500 \
  --resource-type dedicated

# Check request status
az quota request status list \
  --scope /subscriptions/<subscription-id>/providers/Microsoft.Compute/locations/eastus
```

**Approval Process:**
- Most adjustable quotas are auto-approved within minutes
- Some requests require manual review (hours to days)
- Non-adjustable quotas require Azure Support ticket

> **📖 See also:** [az quota update](./references/commands.md#az-quota-update), [az quota request status](./references/commands.md#az-quota-request-status-list)

### Workflow 4: List All Quotas for Planning

**Scenario:** Understand all quotas for a resource provider in a region

```bash
# List all compute quotas in East US (table format)
az quota list \
  --scope /subscriptions/<subscription-id>/providers/Microsoft.Compute/locations/eastus \
  --output table

# List all network quotas
az quota list \
  --scope /subscriptions/<subscription-id>/providers/Microsoft.Network/locations/eastus \
  --output table

# List all Container Apps quotas
az quota list \
  --scope /subscriptions/<subscription-id>/providers/Microsoft.App/locations/eastus \
  --output table
```

> **📖 See also:** [az quota list](./references/commands.md#az-quota-list)

## Troubleshooting

### Common Errors

| **Error** | **Cause** | **Solution** |
|-----------|-----------|--------------|
| REST API "No Limit" | REST API showing misleading "unlimited" values | **CRITICAL: "No Limit" ≠ unlimited!** Use CLI instead. See warning above. Check [service limits docs](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits) |
| REST API failures | REST API unreliable and misleading | **Always use Azure CLI** - See [commands.md](./references/commands.md) for complete CLI reference |
| `ExtensionNotFound` | Quota extension not installed | `az extension add --name quota` |
| `BadRequest` | Resource provider not supported by quota API | Use CLI (preferred) or [service limits docs](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits) |
| `MissingRegistration` | Microsoft.Quota provider not registered | `az provider register --namespace Microsoft.Quota` |
| `QuotaExceeded` | Deployment would exceed quota | Request increase or choose different region |
| `InvalidScope` | Incorrect scope format | Use pattern: `/subscriptions/<id>/providers/<namespace>/locations/<region>` |

### Unsupported Resource Providers

**Known unsupported providers:**
- ❌ Microsoft.DocumentDB (Cosmos DB) - Use Portal or [Cosmos DB limits docs](https://learn.microsoft.com/en-us/azure/cosmos-db/concepts-limits)

**Confirmed working providers:**
- ✅ Microsoft.Compute (VMs, disks, cores)
- ✅ Microsoft.Network (VNets, IPs, load balancers)
- ✅ Microsoft.App (Container Apps)
- ✅ Microsoft.Storage (storage accounts)
- ✅ Microsoft.MachineLearningServices (ML compute)

> **📖 See also:** [Troubleshooting Guide](./references/commands.md#troubleshooting)

## Additional Resources

| Resource | Link |
|----------|------|
| **CLI Commands Reference** | [commands.md](./references/commands.md) - Complete syntax, parameters, examples |
| **Azure Quotas Overview** | [Microsoft Learn](https://learn.microsoft.com/en-us/azure/quotas/quotas-overview) |
| **Service Limits Documentation** | [Azure subscription limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits) |
| **Azure Portal - My Quotas** | [Portal Link](https://portal.azure.com/#blade/Microsoft_Azure_Capacity/QuotaMenuBlade/myQuotas) |
| **Request Quota Increases** | [How to request increases](https://learn.microsoft.com/en-us/azure/quotas/quickstart-increase-quota-portal) |

## Best Practices

1. ✅ **Always check quotas before deployment** - Prevent quota exceeded errors
2. ✅ **Run `az quota list` first** - Discover correct quota resource names
3. ✅ **Compare regions** - Find regions with available capacity
4. ✅ **Account for growth** - Request 20% buffer above immediate needs
5. ✅ **Use table output for overview** - `--output table` for quick scanning
6. ✅ **Document quota sources** - Track whether from quota API or official docs
7. ✅ **Monitor usage trends** - Set up alerts at 80% threshold (via Portal)

## Workflow Summary

```
┌─────────────────────────────────────────┐
│  1. Install quota extension             │
│     az extension add --name quota       │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  2. Discover quota resource names       │
│     az quota list --scope ...           │
│     (Match by localizedValue)           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  3. Check current usage                 │
│     az quota usage show                 │
│     --resource-name <name>              │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  4. Check quota limit                   │
│     az quota show                       │
│     --resource-name <name>              │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  5. Validate capacity                   │
│     Available = Limit - (Usage + Need)  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
         ┌────────┴────────┐
         │                 │
    ✅ Sufficient     ❌ Insufficient
         │                 │
         ▼                 ▼
    Proceed          Request increase
                     or change region
```
