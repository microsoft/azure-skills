# App Onboard Prepare — Pricing Guide

> ⛔ **SELF-CHECK:** If `costEstimate.breakdown[]` has ANY `monthlyUsd > 0`, at least one `pricing_get` or `az rest` pricing API call MUST appear in this session. Estimating from memory or training data is NEVER acceptable — reference values in this file may be outdated. If API fails after 2 attempts, use the reference value WITH disclaimer: `"⚠️ Estimated from reference — live API unavailable."`

## Free-Tier Shortcut — Skip API

> ⛔ **Check this FIRST.** If ALL services use free-tier SKUs → write $0 cost estimate, add disclaimer "Estimate assumes usage within free grant limits", skip to Step 7.

| Service | Free SKU | Skip API? |
|---------|----------|-----------|
| App Service | F1 | Yes |
| Static Web Apps | Free | Yes |
| Functions | Consumption (≤1M exec) | Yes |
| Cosmos DB | Free tier (1000 RU/s) | Yes |
| Container Apps | Consumption (≤180K vCPU-s) | Yes |

---

## App Service Quick Reference

| SKU | `skuName` | Monthly |
|-----|-----------|---------|
| B1 Linux | `B1` | ~$13.14 |

> ⛔ **Case-sensitive:** use `B1` not `b1`. Use `skuName` (not `armSkuName`) for Basic/Standard.

---

## How to Use

1. Pick SKU from [sku-matrix.md](sku-matrix.md) based on budget intent.
2. Find service section in [pricing-guide-services.md](pricing-guide-services.md) for filter strings and formulas.
3. Call the pricing router — tool `mcp_azure_mcp_pricing` (VS Code) / `azure-pricing` (CLI) — with `intent`, `command: "pricing_get"`, and a `parameters` object (NOT `--flags`). Parallel OK. ⛔ At least one filter inside `parameters`: `sku`, `service`, `region`, `service-family`, or `filter`. ⛔ **`sku` matches `armSkuName`, not `skuName`** — use it ONLY when `armSkuName` is populated (App Service, MySQL/PostgreSQL, Redis). Empty-`armSkuName` services (ACR, Storage, Cosmos, Key Vault) return `[]` or 400 for `sku`/`service` — use a raw `filter` on `serviceName` + `meterName` instead.
4. Apply the monthly multiplier from each meter's `unitOfMeasure` (see § Monthly Multiplier) — NOT a per-service constant.
5. Cross-check returned `retailPrice` against planned SKU.

## Monthly Multiplier — by Meter Unit

⛔ **Read `unitOfMeasure` per price record — NEVER blanket `× 730`** (one service mixes units, e.g. ACR returns `1/Day` + `1 Second` + `1 GB/Month`):

| `unitOfMeasure` | Monthly formula |
|-----------------|-----------------|
| `1 Hour` / `1/Hour` | `retailPrice × 730` |
| `1/Day` / `1 Day` | `retailPrice × 30` |
| `1 GB/Month` | `retailPrice × estimatedGB` (already monthly) |
| `1 Second` / `1 GiB Second` | `retailPrice × activeUnitsPerMonth` (usage-based) |
| `10K` / `1M` operations | `retailPrice × estimatedOps ÷ unitSize` |

## Usage-Based Services

When AI/OpenAI/LLM components detected: add `"💸 Usage-based — excluded from total"` to `costEstimate.breakdown[]` and `"⚠️🤖 AI inference costs excluded"` to `assumptions[]`. Surface at EVERY approval gate.

## Service Pricing Reference

See [pricing-guide-services.md](pricing-guide-services.md) for per-service filter strings, meter names, and monthly formulas.

**Key rules:**
- `armSkuName` is empty for most PaaS — filter by `meterName` or `productName`
- Monthly multiplier: read `unitOfMeasure` (§ Monthly Multiplier) — never assume ×730
- Functions Consumption / Static Web Apps: not in API
- Default `isPrimaryMeterRegion eq true` + `priceType eq 'Consumption'` — but check the service section in [pricing-guide-services.md](pricing-guide-services.md) first; some drop `isPrimaryMeterRegion` (Service Bus, Cosmos 100 RU/s, Redis Basic).
- Service names are case-sensitive

## Troubleshooting

When `pricing_get` returns empty: (1) Check `armSkuName` populated/case-sensitive? (2) HTTP fallback: `https://prices.azure.com/api/retail/prices?$filter={filter}`. (3) After 2 failures, use [pricing-guide-services.md](pricing-guide-services.md) with disclaimer. (4) Log to `costEstimate.apiFailures[]`.

> ⛔ **Never claim user has free credits remaining.** Use: "Check balance at portal."

