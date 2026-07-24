# Prepare Phase — MCP Tools

Phase-exclusive tool parameters for the prepare phase. For shared tools (`subscription_list`, `group_list`, `get_azure_bestpractices`, `extension_cli_install`), see [mcp-tool-reference.md](../../references/mcp-tool-reference.md).

> **Troubleshooting:** If a tool call fails with unknown parameter or missing command errors, consult the official docs: <https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/>

---

## `mcp_azure_mcp_pricing` (hierarchical)

| Sub-command | Required Params | Optional Params | Read-Only |
|-------------|----------------|-----------------|-----------|
| `pricing_get` | *(none)* | `service` (service name, e.g. "Azure App Service"), `sku` (`armSkuName` value), `region` (ARM region name), `currency` (e.g. "USD"), `filter` (OData filter for retail prices API) | ✅ |

**Usage:** Query Azure retail pricing. Use `service` + `region` for broad queries, `sku` for exact SKU lookup (when `armSkuName` is populated — e.g., Redis Cache, App Service Premium). Use `filter` for advanced OData queries against the retail prices API. See [pricing-guide.md](pricing-guide.md) for per-service filter strings and meter name mappings.

## `mcp_azure_mcp_quota` (hierarchical)

> ⛔ **Do NOT use for AppOnboard quota checks.** Use `az rest` with the Quota REST API instead — see [sku-quota-validation.md](sku-quota-validation.md). The MCP quota tool returns misleading "No Limit" values for unsupported resource types — "No Limit" means the quota API doesn't support that resource type, NOT unlimited capacity.

| Command | Required Params | Optional Params | Read-Only |
|---------|----------------|-----------------|-----------|
| `quota_usage_check` | `region`, `resource-types` (ARM type, e.g. `Microsoft.Compute/virtualMachines`) | `subscription` | ✅ |
| `quota_region_availability_list` | `resource-types` (ARM type) | `subscription` | ✅ |

## `mcp_azure_mcp_cloudarchitect` (hierarchical)

| Sub-command | Required Params | Optional Params | Read-Only |
|-------------|----------------|-----------------|-----------|
| `cloudarchitect_design` | *(none)* | `question`, `question-number`, `total-questions`, `answer`, `next-question-needed` (bool), `confidence-score` (0.0–1.0), `state` (JSON — tracks architectureComponents, architectureTiers, requirements{explicit,implicit,assumed}, confidenceFactors) | ✅ |

**Usage:** Multi-turn conversational tool. For single-shot use, populate `state` with known requirements, set `confidence-score` ≥ 0.7 and `next-question-needed: false` to get a direct recommendation without follow-ups.

## `mcp_azure_mcp_wellarchitectedframework` (hierarchical)

| Sub-command | Required Params | Optional Params | Read-Only |
|-------------|----------------|-----------------|-----------|
| `wellarchitectedframework_serviceguide_get` | *(none)* | `service` (case-insensitive, hyphens/underscores/spaces OK, e.g. "cosmos-db", "App Service", "cosmosdb") | ✅ |

**Usage:** Omit `service` to list all supported services. Provide `service` to get per-service guidance across all 5 WAF pillars.

## `mcp_azure_mcp_advisor` (hierarchical)

| Sub-command | Required Params | Optional Params | Read-Only |
|-------------|----------------|-----------------|-----------|
| `advisor_recommendation_list` | *(none)* | `subscription`, `resource-group` | ✅ |

## `mcp_azure_mcp_group_resource_list`

| Required | Optional | Read-Only |
|----------|----------|-----------|
| `resource-group` | `subscription`, `tenant` | ✅ |

Returns: resource names, IDs, types, locations within the group.

## `mcp_azure_mcp_policy` (hierarchical)

| Sub-command | Required Params | Optional Params | Read-Only |
|-------------|----------------|-----------------|-----------|
| *(subscription scope)* | *(none)* | `subscription` | ✅ |

**Usage:** Bulk fetch subscription policy constraints — blocked resource types, required tags, allowed regions. Use in prepare Step 2 alongside `advisor_recommendation_list` to surface governance constraints early.

---

## Phase 2 Tool Map

| Tool | Sub-command | AppOnboard Step | Purpose |
|------|-----------|----------|---------|
| `mcp_azure_mcp_cloudarchitect` | `cloudarchitect_design` | Step 3 | Architecture validation. Single-shot: populate `state` from `context.json`, set `confidence-score: 0.8` |
| `mcp_azure_mcp_wellarchitectedframework` | `wellarchitectedframework_serviceguide_get` | Step 4 | Per-service WAF guidance. Call with `service: "{service-name}"` for each planned service |
| `mcp_azure_mcp_advisor` | `advisor_recommendation_list` | Step 2 | Get existing subscription recommendations alongside policy query |
| `mcp_azure_mcp_policy` | *(hierarchical)* | Step 2 | Subscription policy constraints — blocked types, required tags, allowed regions |
| `mcp_azure_mcp_pricing` | `pricing_get` | Step 6 | Cost estimation. Read [pricing-guide.md](pricing-guide.md) first |
| `mcp_azure_mcp_quota` | ⛔ Do NOT use | Step 5 | ⛔ Read [sku-quota-validation.md](sku-quota-validation.md) and use `az rest` with Quota REST API instead |
| `mcp_azure_mcp_subscription_list` | *(flat)* | Step 1 | Resolve target subscription if not in context |
| `mcp_azure_mcp_group_list` | *(flat)* | Step 7 | List existing RGs for reuse/conflict detection |
| `mcp_azure_mcp_group_resource_list` | *(flat)* | Step 7 | Detect naming collisions in target RG |

---

## Tool Pitfalls

- **`mcp_azure_mcp_pricing` → `pricing_get`:** Use `--sku` when querying by `armSkuName` (e.g., Redis Cache, App Service Premium). For services without `armSkuName`, use `filter` and `meterName` matching instead. Omitting all filter params returns too many results.
