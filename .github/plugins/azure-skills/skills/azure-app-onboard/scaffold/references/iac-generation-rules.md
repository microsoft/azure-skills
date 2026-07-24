# IaC Generation Rules — Steps 5–8

Rules for generating infrastructure code, Dockerfiles, security verification, and telemetry wiring.

## Step 5 — Generate IaC

For each service in `services[]`:

> **Sub-agent delegation:** Use [subagent-iac-gen.md](subagent-iac-gen.md) template verbatim. Include full `prepare-plan.json`, `ScaffoldManifest` interface, and compute-target patterns. Self-review (Step 9) remains mandatory after sub-agent returns.

> **PostgreSQL wiring:** Include firewall rule + extension allow-list (see [subagent-iac-gen.md](subagent-iac-gen.md) Step 6 if PostgreSQL in plan). ⛔ **PostgreSQL config resources** (e.g., `require_secure_transport`) must use `source: 'user-override'` — `'system-default'` is read-only and ARM rejects it. ⛔ **Do NOT create `databases/postgres` child resource** — it exists by default and ARM rejects duplicate creation. **BuildKit Dockerfiles:** Generate `Dockerfile.azure` for ACR compatibility — see [code-deployment-container-apps.md § BuildKit](../../deploy/references/code-deployment-container-apps.md).

> **Env var completeness:** Read `.env.example` (or `.env.sample`, `config.example`) + config/settings files (Pydantic `Settings`, `@t3-oss/env-nextjs`, Django `settings.py`) for each component to enumerate required env vars before generating IaC. Every env var with a placeholder value (not `localhost`) should map to either: (1) a Bicep parameter, (2) a KV secret reference, or (3) a hardcoded value derived from other resources (e.g., database connection string from the DB module output). ⛔ **Container Apps:** KV `secretRef` entries must be gated behind `isPlaceholder` — Phase 1 = `secrets: []`, Phase 2 activates KV refs. See [bicep-container-apps.md](bicep-container-apps.md). Flag unmapped vars in selfReview as ⚠️ WARN. Missing vars cause container crash loops at deploy time.

> ⛔ **Set `targetScope = 'subscription'` in `main.bicep`.** Subscription-scope Bicep creates the resource group in IaC with all 5 AppOnboard tags (including `created-at`). Do NOT use default resource-group scope — it requires imperative `az group create` which consistently misses tags. If the user lacks subscription-level permissions, the deploy phase handles fallback to RG-scope automatically.

> ⛔ **Native module deploy strategy.** If `prepare-plan.json.deployStrategy` exists, read [bicep-app-service.md § Native Module Deploy Strategy](bicep-app-service.md) and apply the startup command + app settings to the App Service Bicep. The `deployStrategy.startupCommand` goes into `appCommandLine`, and `deployStrategy.requiredAppSettings` goes into `appSettings[]`. When no `deployStrategy` exists, do NOT set `appCommandLine` — let Oryx use its default startup.

### Session Tags — Mandatory on ALL Resources

⛔ Include the 5 AppOnboard tags on every resource and module. See [bicep-patterns.md § tags](bicep-patterns.md) for Bicep code block or [terraform-patterns.md § tags](terraform-patterns.md) for HCL code block.

| Tag key | Value source |
|---------|-------------|
| `app-onboard-skill` | `'true'` |
| `app-onboard-session-id` | `sessionId` param |
| `created-at` | ISO timestamp (scaffold populates, deploy may override) |
| `environment` | `naming.resourcePrefix` |
| `deployed-by` | `context.json.azure.userDisplayName` |

If extending existing IaC, MERGE with existing tags using `union()` / `merge()`.

> ⛔ **Do NOT generate `azure.yaml`.** Deploy via `az deployment sub create`. See [pipeline-rules.md](../../references/pipeline-rules.md) § azure.yaml prohibition.

### Verification

⛔ **API version verification:** Use versions from `apiVersions` input map. If a type is missing from the map, use the latest GA version from reference file examples — no `-preview` suffix. `az bicep build` catches invalid versions at compile time.

⛔ **Resource property verification:** Training data references deprecated properties. Known traps: `Microsoft.CognitiveServices/accounts/deployments` uses `sku` (name + capacity), NOT `scaleSettings` (deprecated) — omit `raiPolicyName`; Key Vault `enablePurgeProtection` — omit entirely (`false` rejected by ARM, `true` blocks cleanup). Fallback: `az bicep build` + `what-if`.

### Output

`infra/main.bicep`, `main.parameters.json`, `modules/{service}.bicep` per service.

### Platform Compatibility

- **Line endings:** Generated `.bicep` files need LF, not CRLF — Bicep triple-quoted strings pass content literally to ARM, and `\r` bytes crash `/bin/sh` in containers. The validate subagent runs `mcp_bicep_format_bicep_file` (or `bicep-format_bicep_file`) post-generation to enforce this. If the formatter is unavailable, ensure files use LF manually.
- **Shell compatibility:** Startup scripts in Bicep multiline strings MUST use `set -eu` (POSIX). Do NOT use `set -euo pipefail` — Container Apps base images use `/bin/sh` (dash), not bash.
- **Package manager pinning:** When generating or modifying Dockerfiles, pin package manager versions from the project's `packageManager` field (e.g., `pnpm@9.4.0`). Never use `@latest` — major version drift breaks builds on older Node.js base images.

### Security Patterns — Apply During Generation

⛔ Apply ALL patterns from [`bicep-patterns-security.md`](bicep-patterns-security.md) during generation — managed identity, SCM/FTP auth policies, KV secrets, least-privilege RBAC.

## Step 6b — Dockerfile Generation (conditional)

If `prepare-plan.json.services[]` has any entry with `name` containing "Container Apps" AND that component has no existing Dockerfile → ⛔ **You MUST read [`dockerfile-generation.md`](dockerfile-generation.md)** and generate one. Skip if all Container Apps components already have Dockerfiles, or if no service targets Container Apps.

## Step 7 — Secure-by-Default Verification

⛔ Read [`bicep-patterns-security.md`](bicep-patterns-security.md) (or `terraform-patterns.md` § Security Defaults) and verify ALL security patterns from Step 5. If deployment includes compute with MI ↔ resource RBAC, ⛔ read [rbac-roles.md](rbac-roles.md) for GUID table. **If a role is NOT in the table, check [Azure built-in roles docs](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles).** Never guess GUIDs. Skip RBAC for SWA-only.

Tell the user which patterns were applied: managed identity, KV secrets, least-privilege RBAC, SCM/FTP auth policies, private endpoints.

## Step 8 — Wire Telemetry

If `prepare-plan.json.instrumentation.appInsightsEnabled` is `true`, add `APPLICATIONINSIGHTS_CONNECTION_STRING` as a plain app setting wired from the App Insights module output. The connection string is not a secret — no KV storage needed. For Container Apps: use a plain env var (not `secretRef`).
