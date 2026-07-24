# Naming Patterns

Per-resource naming rules for AppOnboard-generated Azure resources. Apply in Step 7 (Generate naming).

> **Reference:** [Azure naming conventions](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming) — link, don't duplicate. Check docs for updates.

## Default Pattern

```
{abbreviation}-{resourcePrefix}
```

Where `resourcePrefix` = `{project}-{env}-{suffix}` (generated once in prepare Step 7, stored in `prepare-plan.json.naming.resourcePrefix`).

- `{project}` — app name from `context.json.app.name` (lowercase, alphanumeric + hyphens)
- `{env}` — `dev` / `staging` / `prod` (from intent or default `dev`)
- `{suffix}` — first 4 chars of session UUID (e.g., `a1d5`). Generated once, stored in `naming.suffix`
- `{abbreviation}` — short service prefix from the table below (e.g., `app`, `kv`, `rg`)

**Examples with `resourcePrefix = myapp-dev-a1d5`:**
- Resource Group: `rg-myapp-dev-a1d5`
- App Service: `app-myapp-dev-a1d5`
- Key Vault: `kv-myapp-dev-a1d5`
- Storage: `stmyappdeva1d5` (alphanumeric only)

> ⛔ **No redundancy.** The resource name is `{abbr}-{resourcePrefix}` — NOT `{project}-{abbr}-{project}-{env}-{suffix}`. The project name appears ONCE in the prefix.
>
> ⛔ **Scaffold reads naming from the plan — does NOT generate or modify resource names.**

Override via `context.json.overrides[]` with `key: "naming.pattern"`.

## Per-Resource Rules

| Resource | Abbreviation | Max Length | Allowed Chars | Globally Unique? | Example |
|----------|-------------|------------|---------------|------------------|---------|
| Resource Group | `rg` | 90 | Alphanumeric, hyphens, underscores, periods, parens | No (but include suffix to avoid cross-session collisions) | `rg-myapp-dev-a1d5` |
| App Service | `app` | 60 | Alphanumeric, hyphens | **Yes** | `app-myapp-dev-a1d5` |
| Container App | `ca` | 32 | Lowercase alphanumeric, hyphens | No (within env) | `ca-myapp-dev-a1d5` |
| Container Registry | `cr` | 50 | **Alphanumeric only** | **Yes** | `crmyappdeva1d5` |
| Azure SQL Server | `sql` | 63 | Lowercase alphanumeric, hyphens | **Yes** | `sql-myapp-dev-a1d5` |
| Cosmos DB | `cosmos` | 44 | Lowercase alphanumeric, hyphens | **Yes** | `cosmos-myapp-dev-a1d5` |
| Storage Account | `st` | 24 | **Lowercase alphanumeric only** | **Yes** | `stmyappdeva1d5` |
| Key Vault | `kv` | 24 | Alphanumeric, hyphens | **Yes** | `kv-myapp-dev-a1d5` |
| Log Analytics | `log` | 63 | Alphanumeric, hyphens | No (within RG) | `log-myapp-dev-a1d5` |
| App Insights | `appi` | 260 | Most chars | No (within RG) | `appi-myapp-dev-a1d5` |
| Service Bus | `sb` | 50 | Alphanumeric, hyphens | **Yes** | `sb-myapp-dev-a1d5` |
| Functions | `func` | 60 | Alphanumeric, hyphens | **Yes** | `func-myapp-dev-a1d5` |
| Static Web Apps | `swa` | 40 | Alphanumeric, hyphens | No (suffix still required — Rule 1) | `swa-myapp-dev-a1d5` |
| Redis Cache | `redis` | 63 | Alphanumeric, hyphens | **Yes** | `redis-myapp-dev-a1d5` |

> **CAF deviation:** Azure Cloud Adoption Framework uses `sbns` for Service Bus namespace. AppOnboard uses `sb` for brevity — either is acceptable.

## Rules

1. **ALL resources get the `{suffix}`** — including resource groups. This prevents cross-session naming collisions when the same app is deployed multiple times. The suffix is a 4-char random string generated once per session.
2. **Container Registry + Storage Account:** strip hyphens (alphanumeric only). ⛔ **Mechanical transform — do NOT re-derive char-by-char:** `('cr' + resourcePrefix).replace(/-/g,'').toLowerCase()`, truncate to ≤50 (ACR) / ≤24 (Storage). Worked example: `resourcePrefix = bezkoder-dev-18a3` → `cr` + `bezkoderdev18a3` → `crbezkoderdev18a3`. Copy the pattern; do not spell out the concatenation.
3. **Validate length** after substitution — Key Vault (24 chars) is the tightest constraint. Budget for `{project}`: `24 - len(abbreviation) - len(env) - len(suffix) - 3 - 2` (separators + healing reserve). For `kv` + `dev`: 10 chars max. The 2-char reserve ensures room for a healing suffix (e.g., `edd6` → `edd602`) on region fallback. **Truncation when over budget:**
   1. Truncate at the nearest hyphen boundary within budget (e.g., `broken-web-app` at 10 → `broken-web`)
   2. If no hyphen within budget: hard truncate, no trailing hyphen
   3. Verify truncated name doesn't collide with reserved words (Rule 4)
   4. Recompute ALL resource names with the truncated project — do NOT mix long and short names
4. **Never use reserved words** as resource names (`admin`, `login`, `root`, `test`)
5. Populate `naming.resources[]` in `prepare-plan.json` with concrete names after validation
