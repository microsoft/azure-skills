# Azure VM Recommender

Recommend Azure VM sizes, VM Scale Sets (VMSS), and configurations by analyzing workload type, performance requirements, scaling needs, and budget. No Azure subscription required — data comes from public Microsoft documentation and the unauthenticated Retail Prices API.

## When to Use This Skill

- User asks which Azure VM or VMSS to choose for a workload
- User wants to compare VM families, sizes, or pricing tiers
- User asks about trade-offs (cost vs performance, single VM vs scale set, orchestration modes)
- User needs a cost estimate without an Azure subscription
- User asks "Needs autoscaling?" or wants to decide between a single VM and a scale set

## Workflow

> Use reference files for initial filtering. Then **verify with live documentation** via `web_fetch` before final recommendations. If `web_fetch` fails, fall back to the reference files and surface the staleness warning from [web-fetch-policy.md](references/web-fetch-policy.md).

### Step 1: Gather Requirements

Ask the user (infer when possible):

| Requirement | Examples |
|---|---|
| Workload type | Web server, relational DB, ML training, batch, dev/test |
| vCPU / RAM needs | "4 cores, 16 GB" or "lightweight" / "heavy" |
| GPU needed? | Yes → GPU families; No → general / compute / memory |
| Storage needs | High IOPS, large temp disk, premium SSD |
| Budget priority | Cost-sensitive, performance-first, balanced |
| OS | Linux or Windows (affects pricing) |
| Region | Affects availability and price |
| Instance count | Single, fixed count, or variable |
| Scaling needs | None, manual, autoscale (metrics / schedule) |
| Availability needs | Best-effort, fault-domain, cross-zone HA |
| Load balancing | None, Azure Load Balancer (L4), Application Gateway (L7) |

### Step 2: Determine VM vs VMSS

Review [VMSS Guide](../../references/vmss-guide.md). Decision shortcut — start by asking **Needs autoscaling?** then walk the table:

| Signal | Pick |
|---|---|
| Autoscale on CPU, memory, or schedule | **VMSS** |
| Stateless web/API tier behind a load balancer | **VMSS** |
| Batch / parallel processing across many nodes | **VMSS** |
| Mixed VM sizes in one group | **VMSS (Flexible)** |
| Single long-lived server (jumpbox, AD DC) | **VM** |
| Unique per-instance config | **VM** |
| Stateful, tightly-coupled cluster | **VM** (or VMSS case-by-case) |

If recommending VMSS, verify with `web_fetch` per [web-fetch-policy.md](references/web-fetch-policy.md). When in doubt, default to a single **VM**.

### Step 3: Select VM Family

Review [VM Family Guide](../../references/vm-families.md) and pick 2–3 candidate families. Verify each candidate's specs with `web_fetch` against:

```
https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/<family-category>/<series-name>
```

For Spot eligibility, also fetch `https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/use-spot`. If any fetch fails, follow [web-fetch-policy.md](references/web-fetch-policy.md). Same SKUs apply to single VMs and VMSS.

### Step 4: Look Up Pricing

Query the Azure Retail Prices API per [Retail Prices API Guide](../../references/retail-prices-api.md).

> **VMSS:** no extra charge — pricing is per-VM. Multiply per-instance price × expected count. For autoscale, estimate at both `min` and `max`.

### Step 5: Validate Quota Availability

> **GATE — do not present recommendations until quota is validated.**

If the user has a subscription + region, review and run the checks from [VM Quota Validation Guide](../../references/vm-quotas.md). Without a subscription, note quota must be checked before deployment.

| Outcome | Action |
|---|---|
| ✅ Sufficient | Proceed to Step 6 |
| ⚠️ Near limit (>80%) | Proceed but warn; suggest quota increase |
| ❌ Insufficient | Request increase, swap family, or try another region |

Include a "Quota Status" column (✅/⚠️/❌) in the table.

### Step 6: Present Recommendations

Provide **2–3 options** with trade-offs:

| Column | Purpose |
|---|---|
| Hosting Model | VM or VMSS (with orchestration mode if VMSS) |
| VM Size | ARM SKU name (e.g., `Standard_D4s_v5`) |
| vCPUs / RAM | Core specs |
| Instance Count | `1` for VM; `min–max` for VMSS with autoscale |
| Estimated $/hr | Per-instance pay-as-you-go |
| Why | Workload fit |
| Trade-off | What the user gives up |

Always explain *why* a family fits and the Trade-off (cost vs cores, burstable vs dedicated, VM simplicity vs VMSS scale).

For VMSS, also mention orchestration mode (default **Flexible**), autoscale strategy (metric / schedule / both), and load balancer type.

### Step 7: Offer Next Steps

- Compare reservation / savings plan pricing (`priceType eq 'Reservation'` in the API)
- Suggest [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) for full estimates
- For VMSS: [autoscale best practices](https://learn.microsoft.com/azure/azure-monitor/autoscale/autoscale-best-practices), [VMSS networking](https://learn.microsoft.com/azure/virtual-machine-scale-sets/virtual-machine-scale-sets-networking)

### Step 8: Hand Off to VM Creator (Optional)

If the user wants to **actually provision** what was recommended, hand off to [vm-creator](../vm-creator/vm-creator.md). See [handoff-to-creator.md](references/handoff-to-creator.md) for the required Plan Card render and routing rules.

## Error Handling

| Scenario | Action |
|---|---|
| API returns empty results | Broaden filters — check `armRegionName`, `serviceName`, `armSkuName` spelling |
| User unsure of workload type | Ask clarifying questions; default to General Purpose D-series |
| Region not specified | Use `eastus` as default; note prices vary by region |
| Unclear if VM or VMSS needed | Ask about scaling + instance count; default to single VM if still unsure |
| User asks VMSS pricing directly | Same VM pricing API; VMSS has no extra charge — multiply by instance count |

## References

- [VM Family Guide](../../references/vm-families.md) — family-to-workload mapping
- [Retail Prices API Guide](../../references/retail-prices-api.md) — query patterns, filters
- [VMSS Guide](../../references/vmss-guide.md) — when to use VMSS, orchestration, autoscale
- [VM Quota Validation Guide](../../references/vm-quotas.md) — vCPU checks, CLI commands
- [web-fetch-policy.md](references/web-fetch-policy.md) — fail-safe behavior for live docs lookups
- [handoff-to-creator.md](references/handoff-to-creator.md) — Step 8 hand-off rules
- [vm-creator](../vm-creator/vm-creator.md) — provision the recommended SKU
