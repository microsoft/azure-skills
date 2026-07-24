# SKU Selection Matrix

Select SKU based on `context.json.intent.budget`. Cross-reference with `intent.scale` for right-sizing.

## Budget Tiers

> ⚠️ **F1 (Free) limitations:** 1 GB RAM, shared compute (60 min/day CPU), no custom domain, no always-on, no deployment slots, no VNet integration. Only suitable for low-traffic dev/test. Production apps → B1 minimum.

| Service | cost-optimized | balanced | performance |
|---------|---------------|----------|-------------|
| Container Apps | Consumption (scale-to-zero) | Consumption | Dedicated |
| App Service | F1 (Free) | B1 / S1 | P1v3 |
| Azure SQL | Basic (5 DTU) | Standard (S0) | Premium / Serverless |
| Cosmos DB | Serverless | Provisioned (400 RU) | Provisioned (autoscale) |
| Storage | Standard_LRS | Standard_GRS | Premium_LRS |
| Static Web Apps | Free | Standard | Standard |
| Key Vault | Standard | Standard | Premium (HSM) |
| Service Bus | Basic | Standard | Premium |
| Redis Cache | Basic C0 | Standard C1 | Premium P1 |
| Functions | Consumption | Flex Consumption | Premium EP1 |
| Log Analytics | PerGB2018 | PerGB2018 | PerGB2018 (dedicated cluster) |

> ⚠️ **Log Analytics `Free` SKU is deprecated.** ARM rejects it with some API versions and retention settings. Always use `PerGB2018` — first 5 GB/month is free anyway.

## Modifier Rules

- `intent.scale = "Large"` (100K+ users) → bump minimum one tier above cost-optimized
- `intent.budget = "performance"` + `intent.scale = "Small"` → don't over-provision; use balanced tier
- Policy denies a SKU → fall back to next available tier, add to `assumptions[]`
- Cosmos DB Serverless: max 1K RU/s burst, no geo-replication — only for intermittent/dev workloads. Sustained read-heavy → Provisioned.

## Default Behavior

- Single-component app + cost-optimized → cheapest viable SKU (App Service F1, Static Web Apps Free)
- Simple web app with no DB → $0–$15/month
- Always output exact SKU codes: "App Service F1 (Free)" not "Free tier"

## Auto-Cheapest for Fast-Track

⛔ **If `prereq-output.json.fastTrackEligible == true` AND `context.json.intent.budget` is unset, treat as `cost-optimized`.** Fast-track means single-component + no DB + no auth + no Dockerfile — by definition this app fits the cheapest tier. Pick App Service F1 (Free) for dynamic apps that need a runtime (Node.js/Python starter templates), or Static Web Apps Free for pure static HTML/JS/CSS with no server-side runtime. The user still sees the SKU + monthly cost in the scaffold approval gate — they can override via "Edit plan" if they want to upgrade. Do NOT ask the user about budget unless they mention cost first (per [intent-gathering.md](../../references/intent-gathering.md)).

⛔ **Fast-track free promise can degrade.** If the cheapest free tier is unavailable during deploy prep (no F1 quota AND Static Web Apps Free cap reached — see [sku-quota-validation.md](sku-quota-validation.md) § After Checking), degrade to the **cheapest AVAILABLE** tier — do NOT name or assume a specific paid SKU; let the live quota results decide which is cheapest-available. Record an `assumptions[]` note that states clearly WHY fast-track could not stay free, so the approval gate presents the plan with the resulting cost instead of silently upgrading.
