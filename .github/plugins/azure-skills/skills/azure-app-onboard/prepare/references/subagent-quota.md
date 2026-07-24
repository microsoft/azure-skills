# Subagent Template — Quota Validation (Step 5)

Validate SKU quota and offer restrictions across candidate regions before presenting region choices.

## Critical Rules

- ⛔ **Do NOT invoke ANY skills** — no `{"skill": "azure-validate"}`, `{"skill": "azure-prepare"}`, or any other skill call. You are a quota-check subagent only.
- **Read [`sku-quota-validation.md`](sku-quota-validation.md) before executing ANY quota or offer restriction check.** It contains the per-provider API patterns, anti-patterns to avoid, offer restriction checks for database services, region selection logic, and output schema. All procedures live there — follow them exactly.

## Input (provided by caller)

| Field | Required |
|-------|---------|
| `subscriptionId` | YES |
| SKU list from Step 4 (service type + SKU per service) | YES |
| Restricted-offer services (PostgreSQL, MySQL) | If present in plan |
| **Detected DB version per DB service** (from `context.json.detectedServices[]`, e.g. MySQL `5.7`) | ⛔ REQUIRED if a DB is in the plan — the version-selection algorithm in [`sku-quota-validation.md`](sku-quota-validation.md) needs it. |

## Output

Return JSON (≤500 tokens):
```jsonc
{
  "quotaResults": [
    {
      "region": "{checked region}",
      "services": [
        { "service": "{provider}", "sku": "{sku}", "limit": "{from API}", "used": "{from API}", "available": "{limit - used > 0}" },
        // if DB service: add "offerRestricted": "{from capabilities API}", "version": "{selected per sku-quota-validation.md — exact patch, never major-only '8.0'}"
      ],
      "allAvailable": "{true only if ALL services in this region have available=true}"
    }
    // one entry per checked region
  ],
  "recommendedRegion": "{first region where allAvailable=true}",
  "checkedRegions": ["{all regions checked}"],
  "offerRestrictions": [
    // one entry per DB service+region checked — derive from capabilities API response
    { "provider": "{namespace}", "region": "{region}", "restricted": "{true if blocked}", "reason": "{from API or null}" }
  ],
  "offerRestrictionsVerified": "{true only if every DB service from input has ≥1 entry in offerRestrictions[]}"
}
```

⛔ **Caller:** copy each DB service's returned `version` into `prepare-plan.json.services[].version` at plan-write — scaffold needs the exact patch (ARM rejects major-only `'8.0'`).

## Workflow

1. Read [`sku-quota-validation.md`](sku-quota-validation.md)
2. Run the per-provider quota checks for every SKU across all candidate regions
3. If restricted-offer services are in the input, run the offer restriction check for each database service in each candidate region per `sku-quota-validation.md` § Offer Restriction Check
4. Return results per the Output schema above (≤500 tokens)

## Anti-Patterns (from sku-quota-validation.md — repeated here as guardrails)

- ⛔ `az vm list-usage` — wrong provider, misleading data
- ⛔ `az appservice list-locations` — lists locations, NOT quota
- ⛔ `az appservice list-usages` — wrong scope
- ⛔ `mcp_azure_mcp_quota` — unreliable for App Service
- ⛔ `az quota list` — extension loading fails on Windows
- ⛔ Use `az rest` for ALL quota checks

## Rules

- ⛔ Free ≠ unlimited — F1, Consumption, Serverless all have per-subscription, per-region quotas
- ⛔ Check BOTH limit AND current usage — `limit=1, usage=1` means FULL
- ⛔ For PostgreSQL/MySQL: run offer restriction check per `sku-quota-validation.md` § Offer Restriction Check

## Token Budget

≤500 tokens for quota results report.
