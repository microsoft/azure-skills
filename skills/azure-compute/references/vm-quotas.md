# VM Quota Validation Guide

Check Azure VM/VMSS quota availability before recommending or deploying. Ensures the subscription and region have sufficient vCPU capacity.

> ⚠️ **NEVER use the `azure-quota` MCP server as as It is unreliable.** Always try `az quota` CLI commands first.

## Quota Structure

VM quotas are tracked at **two levels** under `Microsoft.Compute`:

| Quota Level | Resource Name | What It Limits |
|---|---|---|
| **Total Regional** | `cores` | All vCPUs across all families in a region |
| **Per-Family** | e.g., `standardDSv3Family` | vCPUs for a specific VM family |

> ⚠️ **Both levels must have capacity.** A deployment fails if either is exceeded.

### Common Quota Resource Names

See [vm-families.md](./vm-families.md) for quota resource names per VM family. Use `az quota list` to discover names not listed there.

> ⚠️ **Do NOT guess quota names from SKU names.** Use `az quota list` to discover correct resource names.

## Quota Check Workflow

### Option A: `az vm list-usage` (Recommended for VM quotas)

No extension required. Returns **both current usage and limit in a single call** for all VM families in a region — equivalent to running `az quota usage show` and `az quota list` together for VM vCPU quotas.

```bash
# All VM family quotas in a region
az vm list-usage --location <region> -o table

# Filter to a specific family
az vm list-usage --location <region> --query "[?contains(name.value,'<quotaName>')].{Name:name.localizedValue, QuotaName:name.value, Current:currentValue, Limit:limit}" -o table
```

> 💡 **Tip:** `az vm list-usage` is the simplest way to check VM quotas. Use `az quota` (Option B) when you need to **request quota increases** or manage quotas for non-VM resource types.

### Option B: `az quota` CLI (For quota increases or non-VM resources)

Prerequisite: `az extension add --name quota`

| Step | Command | Purpose |
|---|---|---|
| 1. Discover names | `az quota list --scope /subscriptions/<sub-id>/providers/Microsoft.Compute/locations/<region> -o table` | Find quota resource name for the VM family |
| 2. Check usage | `az quota usage show --resource-name <name> --scope ...` | Current vCPU consumption |
| 3. Check limit | `az quota show --resource-name <name> --scope ...` | Maximum allowed vCPUs |
| 4. Check regional | Repeat steps 2–3 with `--resource-name cores` | Total regional vCPU cap |

### Calculate Capacity

```text
Available = Limit - Current Usage  (check both family AND regional)
vCPUs Needed = vCPUs per VM × Instance Count

✅ Deploy if: vCPUs Needed ≤ min(Family Available, Regional Available)
❌ Blocked if: either is exceeded
```

**Example:** 3× `Standard_D4s_v5` (4 vCPUs each) = 12 needed. Family: 100−40 = 60 ✅. Regional: 350−280 = 70 ✅.

## Handling Insufficient Quota

| Option | Action |
|---|---|
| **Request increase** | `az quota update --resource-name <name> --scope ... --limit-object value=<new-limit> --resource-type dedicated`. Most increases auto-approve within minutes. |
| **Try different region** | Run the quota check workflow against alternative regions to find available capacity |
| **Switch VM family** | Recommend an alternative family with quota (e.g., D-series full → Dads v5 AMD variant) |

## VMSS Considerations

For scale sets, validate against **autoscale maximum**: `vCPUs per VM × Max Instance Count`.

| Autoscale Setting | vCPUs to Validate |
|---|---|
| Fixed count (5 instances) | vCPUs × 5 |
| Autoscale min=2, max=10 | vCPUs × 10 |

## Error Reference

| Error | Cause | Action |
|---|---|---|
| `QuotaExceeded` | Family vCPU limit reached | Request increase or change family/region |
| `OperationNotAllowed` | Subscription lacks capacity | Request quota increase |
| `cores` limit hit | Regional vCPUs exhausted | Request regional increase |
| CLI commands fail entirely | Auth/extension issue | Use MCP fallback (see below) |

## Related Resources

- Invoke the **azure-quotas** skill for complete quota CLI workflows across all Azure providers
- [VM Family Guide](vm-families.md) — Family-to-workload mapping
- [Azure VM quotas documentation](https://learn.microsoft.com/en-us/azure/virtual-machines/quotas)
