# Azure Cache for Redis → Azure Managed Redis (AMR) Migration

> **Target for both paths**: Azure Managed Redis (AMR) — M, B, X (Flash), A series
> **Source determines which dedicated skill to install** — see decision table below.

There are **two distinct migration paths** to AMR, depending on the source SKU. Each path is owned by a dedicated, versioned skill maintained by the Azure Managed Redis team. The `azure-upgrade` skill does **not** ship the SKU specs, pricing scripts, ARM automation, or template-transformation logic needed for either migration — it routes the user to the correct dedicated skill.

## Decision Table — Which Skill?

| Source SKU | ARM Resource Type | CLI / PowerShell | Dedicated Skill | Repo |
|---|---|---|---|---|
| **ACR / OSS Redis** — Basic, Standard, Premium (C0–C6, P1–P5) | `Microsoft.Cache/redis` | `az redis`, `*-AzRedisCache` | `amr-migration-skill` | https://github.com/AzureManagedRedis/amr-migration-skill |
| **ACRE** — Enterprise (`Enterprise_E*`), Enterprise Flash (`EnterpriseFlash_F*`) | `Microsoft.Cache/redisEnterprise` | `az redisenterprise`, `*-AzRedisEnterprise*` | `acre-to-amr-migration-skill` | https://github.com/AzureManagedRedis/acre-to-amr-migration-skill |

> ACR and ACRE are **fundamentally different products** with different ARM resource types, different APIs, and different migration mechanics. Picking the wrong skill will give the user wrong guidance. Always disambiguate before pointing.

## Disambiguation — How to Tell ACR from ACRE

Ask the user, or inspect the resource. Any **one** of these signals identifies the source:

**ACR (OSS) indicators** → use `amr-migration-skill`:
- Resource type `Microsoft.Cache/redis` (no "Enterprise" suffix)
- SKU names `Basic`, `Standard`, `Premium`, or sizes `C0`–`C6`, `P1`–`P5`
- CLI: `az redis ...` commands
- PowerShell: `New-AzRedisCache`, `Get-AzRedisCache`, etc.
- DNS suffix `.redis.cache.windows.net`
- Default TLS port `6380`

**ACRE indicators** → use `acre-to-amr-migration-skill`:
- Resource type `Microsoft.Cache/redisEnterprise`
- SKU names starting with `Enterprise_` (e.g. `Enterprise_E10`, `Enterprise_E20`) or `EnterpriseFlash_` (e.g. `EnterpriseFlash_F300`)
- CLI: `az redisenterprise ...` commands
- PowerShell: `New-AzRedisEnterpriseCache`, `Get-AzRedisEnterpriseCache`, etc.
- Default TLS port `10000`
- May reference geo-replication groups (`databases create-replica-link`), Private Endpoints, or Private Link DNS zones

If the user has a **mix of ACR and ACRE** resources, both skills should be installed and run separately on the relevant resources. Most users (~97% of the Azure Cache for Redis fleet) are on ACR; ACRE is the smaller (~3%) but functionally distinct case.

## What Each Skill Provides

### `amr-migration-skill` (ACR/OSS → AMR)

- SKU mapping ACR Basic/Standard/Premium → AMR M/B/X/A with validated SKU specs
- Real-time pricing scripts (PowerShell + bash) with HA, clustering, and MRPP logic
- Cache metrics assessment (default 7-day window) for sizing
- Automated migration via ARM REST APIs with **DNS switching** (old hostname keeps working; port still changes)
- Validate-before-migrate workflow with explicit confirmation on destructive actions
- IaC template migration for ARM, Bicep, and Terraform with worked before/after examples
- Feature comparison and retirement FAQ
- **Retirement deadlines this skill addresses**: ACR Basic/Standard/Premium retire **September 30, 2028** (creation blocked for new customers April 1, 2026; for existing customers October 1, 2026)

### `acre-to-amr-migration-skill` (ACRE → AMR)

- Three modes: automation-script update (ARM/Bicep/CLI/PowerShell/Terraform checklist), interactive cache migration with confirmation gates, generic step-by-step guide
- ACRE → AMR SKU resolution via `listSkusForScaling` with fallback mapping table
- In-place migration for standalone caches; create-new-and-swap for geo-replicated caches
- Geo-replication database config parity (eviction policy, modules, etc.)
- Private Endpoint / Private Link migration and DNS zone updates
- Breaking-changes reference (property changes, DNS, API versions)
- Reusable polling scripts (`Poll-MigrationStatus.ps1`, `poll-migration-status.sh`)
- Post-migration ACRE resource cleanup
- **Retirement deadline this skill addresses**: ACRE / Enterprise Flash retire **March 31, 2027**

## Agent Behavior

When a user asks about migrating any flavor of Azure Cache for Redis to Azure Managed Redis:

1. **Do not attempt the migration from this skill.** Neither SKU specs nor migration automation are inlined here.
2. **Determine the source** using the disambiguation signals above. If unclear, ask the user (or inspect the script/resource).
3. **Point the user to the correct dedicated skill** with its repo URL. The repo READMEs include install instructions for GitHub Copilot, Claude Code, and other compatible hosts.
4. After installation, the user's agent will match the dedicated skill on its trigger phrases (e.g. *"migrate my P2 cache to AMR"*, *"convert my Bicep Redis template"*, *"migrate my Enterprise_E10 cache"*, *"update my ACRE ARM template for AMR"*).
5. If the user has **both** ACR and ACRE resources, recommend installing **both** skills and running them on the relevant resources separately.

## Key Migration Facts (so the agent can set expectations)

These are summarized for awareness. For anything operational, defer to the dedicated skills.

### ACR → AMR
- **Port**: 6380 → **10000**. Non-TLS 6379 not supported on AMR.
- **DNS suffix**: `.redis.cache.windows.net` → `<region>.redis.azure.net`
- **Redis version**: 6 → **7.4**
- **No "shards"** in AMR-facing terminology — sharding is internal. Use performance tier (Balanced, Memory Optimized) and size (e.g. B10, M20).
- **Auth**: Recommend adopting **Microsoft Entra ID** post-migration. Entra config is **not** auto-migrated.
- **DNS-switch automated migration** keeps old hostname working, but the port change still applies — apps must be updated.

### ACRE → AMR
- **Same ARM resource type** (`Microsoft.Cache/redisEnterprise`) but property changes apply (see breaking-changes reference in the dedicated skill).
- **Geo-replicated caches** require create-new-and-swap, not in-place migration.
- **Private Endpoints / Private Link** DNS zones must be updated.
- **Database config parity** (eviction policy, modules) must match across replicas before migration.

## Why this is not implemented inline

Both migrations require maintained SKU tables, live pricing or capability lookups, and ARM-level orchestration that is updated independently of the `azure-skills` release cycle. Keeping that logic in two places would drift. The dedicated skill repos are the single source of truth and are versioned independently.

## References

- AMR Migration Skill (ACR → AMR): https://github.com/AzureManagedRedis/amr-migration-skill
- ACRE → AMR Migration Skill: https://github.com/AzureManagedRedis/acre-to-amr-migration-skill
- Azure Managed Redis docs: https://learn.microsoft.com/en-us/azure/redis/managed-redis/
- ACR retirement announcement: https://learn.microsoft.com/en-us/azure/azure-cache-for-redis/cache-retired-tiers
- Entra ID auth for AMR: https://learn.microsoft.com/en-us/azure/redis/managed-redis/managed-redis-entra-for-access-control-configuration
