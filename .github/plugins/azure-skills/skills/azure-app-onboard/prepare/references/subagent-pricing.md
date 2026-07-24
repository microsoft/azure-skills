# Subagent Template — Cost Estimation (Step 6)

Estimate monthly costs for planned Azure services using Azure Retail Prices API.

## References to Read Internally

Read BOTH before making any pricing calls:
- [pricing-guide.md](pricing-guide.md) — methodology, free-tier shortcut, API patterns, troubleshooting
- [pricing-guide-services.md](pricing-guide-services.md) — per-service filter strings, meter names, formulas

## Input (provided by caller)

| Field | Required |
|-------|----------|
| `services[]` with service type and selected SKU per service | YES |
| `region` — deployment region | YES |
| Budget tier (free / balanced / performance) | YES |

## Output

Return JSON (≤500 tokens):
```json
{
  "costEstimate": {
    "monthlyTotal": 42.50,
    "currency": "USD",
    "breakdown": [
      { "service": "App Service", "sku": "B1", "monthlyUsd": 13.14, "formula": "retailPrice × 730" },
      { "service": "PostgreSQL Flexible Server", "sku": "Standard_B1ms", "monthlyUsd": 24.82, "formula": "compute + storage" }
    ],
    "freeGrants": [
      { "service": "Container Apps", "grant": "180K vCPU-sec + 360K GiB-sec", "monthlySavings": 0 }
    ],
    "assumptions": [],
    "disclaimer": "Estimate based on Azure Retail Prices API. Verify at azure.com/pricing."
  }
}
```

## Rules

- ⛔ **Do NOT invoke ANY skills** — no `{"skill": "azure-validate"}`, `{"skill": "azure-prepare"}`, or any other skill call. You are a pricing subagent only. Use direct HTTP to `https://prices.azure.com/api/retail/prices` for price queries (MCP pricing was already attempted inline by the caller).
- ⛔ Check free-tier shortcut FIRST — if ALL services use free SKUs, return $0 with disclaimer
- ⛔ `armSkuName` is case-sensitive — use `B1` not `b1`
- ⛔ For services with empty `armSkuName` (Container Apps, Functions Consumption, ACR, Storage, Cosmos, Key Vault): use `filter`/`meterName` matching — a `sku` filter returns `[]`
- ⛔ **Monthly multiplier = each meter's `unitOfMeasure`** (`1 Hour`→×730, `1/Day`→×30 [ACR/registry, SQL DTU], `1 GB/Month`→×GB, `1 Second`→usage) — NEVER blanket ×730; applying ×730 to a `1/Day` meter overstates ~24×
- ⛔ Use direct HTTP to `https://prices.azure.com/api/retail/prices` for all price lookups. Do NOT use `mcp_azure_mcp_pricing` — it was already tried inline and failed.
- ⛔ Never hardcode dollar amounts — always query live prices
- ⛔ If pricing API returns 400: verify `--sku` included. Free tiers: skip API

## Token Budget

≤500 tokens for cost estimate report.
