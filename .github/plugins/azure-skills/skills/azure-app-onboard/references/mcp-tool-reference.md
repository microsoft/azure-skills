# MCP Tool Reference — Shared Index

Shared tools used across multiple AppOnboard phases, plus the cross-cutting Phase→Tool Map. For phase-specific tools with full parameter tables, see the per-phase references linked below.

> **Troubleshooting:** If a tool call fails with unknown parameter or missing command errors, consult the official docs for current parameter names and allowed values: <https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/>

## Per-Phase Tool References

| Phase | File | Exclusive Tools |
|-------|------|-----------------|
| Prereq | *(shared tools only — see table below)* | *(shared only)* |
| Prepare | [mcp-tools.md](../prepare/references/mcp-tools.md) | pricing, quota, cloudarchitect, WAF, advisor, group_resource_list, policy |
| Scaffold | [mcp-tools.md](../scaffold/references/mcp-tools.md) | bicepschema, all mcp_bicep_*, deploy (iac_rules/pipeline/plan), terraform best practices |
| Deploy | [mcp-tools.md](../deploy/references/mcp-tools.md) | resourcehealth, monitor, appservice, deploy (app_logs/arch_diagram), role |

---

## Global Parameters (all tools)

Every Azure MCP tool accepts these optional parameters in addition to its own:

| Parameter | Description |
|-----------|-------------|
| `subscription` | Azure subscription ID or display name. Defaults to `az account show` default. |
| `tenant` | Entra ID tenant GUID or name. Uses default tenant if omitted. |
| `resource-group` | Resource group name. Required for most resource-specific operations. |

> **Additional global params** (not commonly needed by AppOnboard): `authentication-method` (credential\|key\|connectionString), `max-retries` (default 3), `retry-delay` (default 2s), `retry-delay-maximum` (default 10s), `retry-mode` (fixed\|exponential), `retry-network-timeout` (default 100s). See [official docs](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/) for details.

---

## Shared Tools (used by 2+ phases)

### `mcp_azure_mcp_subscription_list`

| Required | Optional | Read-Only |
|----------|----------|-----------|
| *(none)* | `tenant` | ✅ |

Returns: `subscriptionId`, `displayName`, `state`, `tenantId`, `isDefault`. Use `isDefault: true` as default subscription.

Used by: **prepare** (Step 1), **deploy** (Step 1)

### `mcp_azure_mcp_group_list`

| Required | Optional | Read-Only |
|----------|----------|-----------|
| *(none)* | `subscription`, `tenant` | ✅ |

Returns: resource group names and IDs as JSON array.

Used by: **prepare** (Step 7), **deploy** (Step 3)

### `mcp_azure_mcp_extension_cli_install`

| Required | Optional | Read-Only |
|----------|----------|-----------|
| `cli-type` (az\|azd\|func) | `tenant` | ✅ |

Returns: installation instructions for the specified CLI tool.

Used by: **prereq** (Step 2), **deploy** (Step 3)

### `mcp_azure_mcp_get_azure_bestpractices` (hierarchical)

| Sub-command | Required Params | Optional Params | Read-Only |
|-------------|----------------|-----------------|-----------|
| `get_azure_bestpractices_get` | `resource` (general\|azurefunctions\|static-web-app\|coding-agent), `action` (all\|code-generation\|deployment) | — | ✅ |
| `get_azure_bestpractices_ai_app` | *(none)* | — | ✅ |

**Usage:** `resource` + `action` are both required for `_get`. For `static-web-app` and `coding-agent`, only `action: "all"` is supported.

Used by: **prereq** (Step 3), **scaffold** (Step 5)

---

## Tool Pitfalls

- **`mcp_azure_mcp_subscription_list` is slow at scale:** Returns ALL subscriptions across ALL tenants (238+ in large orgs), causing lengthy picker detours. Use `az account show` for the active subscription (<1 second). Reserve `subscription_list` for prepare Step 1 when the user explicitly wants a different subscription.
