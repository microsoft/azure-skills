# App Onboard Prepare — Per-Service Pricing Patterns

Filter strings, meter names, and formulas per Azure service. For methodology and troubleshooting, see [pricing-guide.md](pricing-guide.md).

### Container Apps

No `armSkuName`. Filter: `serviceName eq 'Azure Container Apps' and armRegionName eq '{region}' and priceType eq 'Consumption' and isPrimaryMeterRegion eq true`

**Key meters:** `Standard vCPU Active Usage` (1 Second), `Standard Memory Active Usage` (1 GiB Second), `Standard Requests` (1M).

**Monthly (Consumption, 1 vCPU, 2 GiB, 8h active/day):**
`(vCPU_active_rate × 3600 × 8 × 30) + (memory_active_rate × 2 × 3600 × 8 × 30)`

**Free grant:** 180K vCPU-sec + 360K GiB-sec + 2M requests/sub/month. Scale-to-zero = $0 idle. When `min_replicas >= 1`: add idle cost from idle meters.

---

### Container Registry (ACR)

Empty `armSkuName` — ⛔ do NOT filter by `sku` (returns `[]`). Filter: `serviceName eq 'Container Registry' and armRegionName eq '{region}' and priceType eq 'Consumption'`, then match `meterName`.

| Tier | `meterName` | `unitOfMeasure` | Monthly |
|------|-------------|-----------------|---------|
| Basic | `Basic Registry Unit` | `1/Day` | `retailPrice × 30` (~$5) |
| Standard | `Standard Registry Unit` | `1/Day` | `retailPrice × 30` (~$20) |
| Premium | `Premium Registry Unit` | `1/Day` | `retailPrice × 30` (~$50) |

⛔ **`1/Day` → × 30, NOT × 730.** The other ACR meters (`Task vCPU Duration` = `1 Second` build compute, `Data Stored` = `1 GB/Month`) are usage-based — exclude from the fixed monthly unless the app builds heavily. ACR Basic fixed cost ≈ **$5/mo**.

---

### App Service

**MCP call:** `pricing_get --service "Azure App Service" --region "{region}"`

**Meter-to-SKU mapping:**

| SKU | `meterName` | Notes |
|-----|-------------|-------|
| F1 | `F1 App` | Free ($0 price) |
| B1 | `B1` | |
| B2 | `B2` | |
| S1 | `S1 App` | |
| P1v3 | `P1 v3 App` | Linux/Windows have different `productName` |

**Gotcha:** `armSkuName` empty for Basic/Standard. Match on `meterName`.

**Monthly:** `retailPrice × 730`

---

### Azure SQL Database

**DTU model** — no `armSkuName`. Filter by `productName` + `meterName`.

| SKU | `productName` contains | `meterName` (unit: 1/Day) |
|-----|----------------------|-------------|
| Basic (5 DTU) | `SQL Database Single Basic` | `B DTU` |
| S0 (10 DTU) | `SQL Database Single Standard` | `S0 DTUs` |
| S1 (20 DTU) | `SQL Database Single Standard` | `S1 DTUs` |

**Monthly (DTU):** `retailPrice × 30`

**vCore model:** `productName` filters — Serverless: `'SQL Database General Purpose - Serverless - Compute Gen5'`. Hyperscale: `'SQL Database Single/Elastic Pool Hyperscale'`. Monthly: `retailPrice × 730`.

---

### Cosmos DB

Filter: `serviceName eq 'Azure Cosmos DB' and armRegionName eq '{region}' and priceType eq 'Consumption' and isPrimaryMeterRegion eq true`

| Model | Match on | Monthly formula |
|-------|----------|----------------|
| Provisioned | `meterName eq '100 RU/s'`, `productName eq 'Azure Cosmos DB'` | `(targetRU / 100) × retailPrice × 730` |
| Autoscale | `productName eq 'Azure Cosmos DB autoscale'`, `meterName` starts with `AP` | varies |
| Serverless | `productName eq 'Azure Cosmos DB serverless'`, `meterName eq '1M RUs'` | `retailPrice × estimatedMillionsOfRU` |

> ⚠️ **Provisioned 100 RU/s gotcha:** The `isPrimaryMeterRegion eq true` entry has `retailPrice: 0` (free-tier placeholder). The real price (~$0.008/hr in eastus) has `isPrimaryMeterRegion: false`. Drop `isPrimaryMeterRegion` from the filter or match on `retailPrice > 0`.

**Storage:** `meterName eq 'Data Stored'` with `productName eq 'Azure Cosmos DB'` (1 GB/Month). Note: this meter has `isPrimaryMeterRegion: false` — drop that filter or query without it.

**Free tier:** 1,000 RU/s + 25 GB per account (one per subscription).

---

### Storage

No `armSkuName`. Filter by `meterName` + `productName`.

**Filter (Hot LRS Blob):**
```
serviceName eq 'Storage' and armRegionName eq '{region}' and meterName eq 'Hot LRS Data Stored' and productName eq 'Blob Storage'
```

**Meter-to-SKU mapping:**

| SKU matrix tier | `meterName` | `productName` |
|----------------|-------------|---------------|
| Standard_LRS | `Hot LRS Data Stored` | `Blob Storage` or `General Block Blob v2` |
| Standard_GRS | `Hot GRS Data Stored` | `Blob Storage` or `General Block Blob v2` |
| Premium_LRS | `Premium LRS Data Stored` | `Premium Block Blob` |

**Monthly:** `retailPrice × estimatedGB`

---

### Key Vault

**Filter:**
```
serviceName eq 'Key Vault' and armRegionName eq '{region}' and priceType eq 'Consumption'
```

**Key meters:**

| Tier | `meterName` | Unit |
|------|-------------|------|
| Standard | `Operations` | 10K |

**Monthly (Standard):** `retailPrice × (estimatedOps / 10000)`. Negligible for typical AppOnboard apps.

---

### Service Bus

**Filter:**
```
serviceName eq 'Service Bus' and armRegionName eq '{region}'
```

> ⚠️ **Do NOT add `isPrimaryMeterRegion eq true`** — all Service Bus meters have `isPrimaryMeterRegion: false`. Adding that filter returns zero useful results.

**Key meters:**

| Tier | `meterName` | Unit | Notes |
|------|-------------|------|-------|
| Basic | `Basic Messaging Operations` | 1M | Usage-based only |
| Standard | `Standard Base Unit` | 1/Hour | Base cost (always-on) |
| Standard | `Standard Messaging Operations` | 1M | Tiered: first 13M free |
| Premium | `Premium Messaging Unit` | 1/Hour | Per messaging unit |

**Monthly (Standard):** `baseUnitRate × 730` + operations beyond free tier. Standard tiered: first 13M free.

**Gotcha:** Standard Base Unit has two entries — hourly and monthly. Use hourly × 730.

---

### Redis Cache

`armSkuName` IS populated — `pricing_get --sku` works.

**MCP call:** `pricing_get --service "Redis Cache" --sku "{armSkuName}" --region "{region}"`

**armSkuName pattern:** `Azure_Redis_Cache_{Tier}_{Size}_Cache` (e.g., `Azure_Redis_Cache_Basic_C0_Cache`, `Azure_Redis_Cache_Standard_C1_Cache`). Query the MCP tool for exact pricing.

**Gotcha:** Basic tier entries have `isPrimaryMeterRegion: false`. The standard filter strips them out. Query by `armSkuName` directly or omit `isPrimaryMeterRegion` and match on `productName eq 'Azure Redis Cache Basic'`.

**Monthly:** `retailPrice × 730`

---

### Azure Database for PostgreSQL Flexible Server

`armSkuName` IS populated — `pricing_get --sku` works. ⛔ **`skuName` is CASE-SENSITIVE:** `B1MS` works, `B1ms` returns 0 results.

**MCP call:** `pricing_get --service "Azure Database for PostgreSQL" --sku "{armSkuName}" --region "{region}"`

**armSkuName values:** ⛔ Case-sensitive. Small Burstable uses short names (`B1MS`, `B2S`); larger Burstable + GP/MO use `Standard_` prefix.

| SKU | `armSkuName` |
|-----|-------------|
| Burstable B1ms | `B1MS` |
| Burstable B2s | `B2S` |
| Burstable B2ms | `Standard_B2ms` |
| General Purpose D2ds_v5 | `Standard_D2ds_v5` |

**Storage:** Query separately — `meterName eq 'Storage Data Stored'` and `productName` containing `Flexible Server Storage`. Unit: 1 GiB/Month. Default 32 GiB included at ~$0.115/GiB/mo.

**Monthly (compute):** `retailPrice × 730`
**Monthly (storage):** `storageRate × storageSizeGB`
**Total:** compute + storage (e.g., B1ms + 32 GiB ≈ $12.41 + $3.68 = ~$16.09)

---

### Functions

**Consumption plan:** Not in API. Free: 1M executions + 400K GB-seconds/month.

**Flex/Premium** — filter: `serviceName eq 'Functions' and armRegionName eq '{region}' and priceType eq 'Consumption' and isPrimaryMeterRegion eq true`
- Flex: `On Demand Execution Time` (1 GB Second), `On Demand Total Executions` (10), `Always Ready Baseline`
- Premium: `Premium vCPU Duration` (1 Hour), `Premium Memory Duration` (1 GiB Hour). Monthly: `vCPU_rate × 730 + memory_rate × GiB × 730`

---

### Static Web Apps

**Not in the Retail Prices API.** Fixed pricing — query [azure.microsoft.com/pricing/details/app-service/static](https://azure.microsoft.com/en-us/pricing/details/app-service/static/):
- **Free tier:** 100 GB bandwidth, 2 custom domains
- **Standard tier:** Flat monthly per app, unlimited bandwidth, 5 custom domains

---

### Log Analytics / Application Insights

**Filter:**
```
serviceName eq 'Azure Monitor' and armRegionName eq '{region}' and priceType eq 'Consumption' and isPrimaryMeterRegion eq true
```

**Key meters:**
- `Platform Logs Data Processed` (unit: 1 GB)
- Log Analytics ingestion — match `meterName` containing `Data Ingestion`

**Free grant:** First 5 GB/month of Log Analytics data ingestion.

**Monthly:** `retailPrice × estimatedGB` (subtract 5 GB free grant).
