# Subagent Template — IaC Generation (Steps 5–8)

Generate deployment-ready IaC from `prepare-plan.json`. Follow the workflow below — each step specifies which reference to read and what to do with it.

## Critical Rules

- ⛔ **Do NOT invoke ANY skills** — no `{"skill": "azure-validate"}`, `{"skill": "azure-deploy"}`, `{"skill": "azure-prepare"}`, or any other skill call. Use the procedures in THIS file only.
- ⛔ **Do NOT generate `azure.yaml`**
- ⛔ **Do NOT modify app source code** — only write files under `infra/` (and `Dockerfile.azure` if needed)
- ⛔ **Do NOT run app build/test/lint commands** (`npm test`, `npm run build`, `pnpm build`, `python -m pytest`, `dotnet build`, etc.). Only validate generated IaC via `az bicep build`.

## Input (provided by caller)

| Field | Source | Required |
|-------|--------|----------|
| `prepare-plan.json` content | Session folder — services, naming, quotas, cost, deploymentVariables | YES (verbatim) |
| `context.json.overrides` | `iacFormat`, `detectedInfraProvider` | YES |
| `buildRequirements` | From `prereq-output.json` — runtime, deps, Dockerfiles | YES |
| `warnings[]` | From `prereq-output.json` — prereq warnings requiring IaC fixes (env var overrides, config changes). Applied during Steps 3–4. | YES |
| Compute targets | App Service/Functions, Container Apps, or both + whether PostgreSQL/Redis present | YES |
| `apiVersions` | Map of `resourceType → latestGAVersion` from main-thread MCP lookup. Use these versions in generated Bicep — do NOT use versions from training data. If `"MCP unavailable"` — see Step 1 for fallback. | YES |

## Output

| Artifact | Location |
|----------|----------|
| `infra/main.bicep` (or `main.tf`) | Workspace `infra/` |
| `infra/main.parameters.json` (or `variables.tf`) | Workspace `infra/` |
| `infra/modules/{service}.bicep` per service | Workspace `infra/modules/` |
| File list | Return to caller for `scaffold-manifest.json.files[]` |

## Workflow

### Step 1 — Read skeleton + tag patterns

Read [bicep-patterns.md](bicep-patterns.md) (Bicep) OR [terraform-patterns.md](terraform-patterns.md) (Terraform) — NOT both.

**Do:** Extract the `main.bicep` skeleton structure (targetScope, parameters, variables, resource group, module calls). Extract the 5-tag block definition. Use `prepare-plan.json.naming` for all resource names — never derive names with `take()`, `substring()`, `uniqueString()`, or string manipulation. The 4-char session suffix in the plan names already provides uniqueness. ⛔ For each `resource 'Type@Version'` declaration, use the version from `apiVersions` input. If type missing from map, use version from reference file examples.

> ⛔ **If `apiVersions` is `"MCP unavailable"` or missing a resource type:** run `az provider show --namespace {ns} --query "resourceTypes[?resourceType=='{type}'].apiVersions[?!contains(@, 'preview')] | [0][0]" -o tsv` for each missing provider — this filters to GA-only and picks the latest. NEVER fall back to training data — hallucinated API versions cause multiple deploy healing cycles.

### Step 2 — Read compute-target patterns

Read ONLY the compute-target reference(s) matching the plan, if the plan has multiple compute targets, read each matching file.:
- If plan has App Service/Functions → read [bicep-app-service.md](bicep-app-service.md).
- If plan has Container Apps → read [bicep-container-apps.md](bicep-container-apps.md).
- If plan has Static Web Apps → read [bicep-swa.md](bicep-swa.md).
- If plan has BOTH → read both.

**Do:** Generate compute module(s) using the patterns from each reference file. F1/D1 App Service: do NOT generate Dockerfile, do NOT add managed identity (OOM). App Service health probe: if `prereq-output.json.healthEndpoint` is non-null, set `siteConfig.healthCheckPath` to that value; otherwise omit (do NOT default to `/`).

### Step 3 — Read security patterns

⛔ **You MUST read [bicep-patterns-security.md](bicep-patterns-security.md).** It contains Key Vault config, managed identity, HTTPS/TLS, and credential hygiene rules. Apply to every generated module.

### Step 4 — Read generation rules

Read [iac-generation-rules.md](iac-generation-rules.md).

**Do:** Apply ALL rules from the reference file to every generated module. The file contains mandatory tag definitions, naming constraints, security patterns, env var completeness checks, and Dockerfile generation rules. Do NOT skip any section — every rule applies.

### Step 5 — Read env var + secrets wiring

Read [env-var-secrets.md](env-var-secrets.md).

**Do:** For each component in the plan, read `.env.example` (or `.env.sample`, config files like Pydantic `Settings`, Django `settings.py`) from the workspace. Map every env var to either: (1) a Bicep parameter, (2) a KV secret reference, or (3) a value derived from other resources (e.g., DB connection string from the DB module output). Wire these into the compute module's `appSettings` (App Service) or `env` (Container Apps).

### Step 6 — Generate data modules (if needed)

ONLY if PostgreSQL, MySQL, or Redis is in the plan. Skip if none are present.

**PostgreSQL Flexible Server module** — include the `AllowAllAzureServicesAndResourcesWithinAzureIps` (`0.0.0.0`) firewall rule, extension allow-list (`azure.extensions` config: `uuid-ossp,pgcrypto,pg_trgm`), SSL enforcement, storage config (default 32 GB). Set the server `version` from `prepare-plan.json.services[].version` (capabilities-verified) — do NOT hardcode or guess. Use `@secure() param administratorLoginPassword` — deploy generates the value once and reuses it on redeploy; do NOT bake a value.

**MySQL Flexible Server module** — mirror the PostgreSQL module, with the MySQL-only deltas: `require_secure_transport: ON` config, the server `version` from `prepare-plan.json.services[].version` (ARM rejects major-only strings like `'8.0'` — needs an exact patch such as `'8.0.21'`), and a `flexibleServers/databases` child resource for the compose-declared DB name (e.g. `MYSQLDB_DATABASE`) so the app's schema DB exists in IaC before the container starts. See [bicep-patterns-data.md § MySQL Flexible Server Module](bicep-patterns-data.md).

**Redis Cache module** — Basic SKU, `enableNonSslPort: false`, `minimumTlsVersion: '1.2'`. Store hostname + access key in Key Vault. ⛔ Known Bicep type issue: `sku` property may cause BCP035/BCP187 warnings — these are false positives. If deploy fails with `InvalidRequestBody` for `properties.sku.name`, create via `az redis create --sku Basic --vm-size c0` then reference with `existing` keyword in Bicep.

Wire connection strings via Key Vault `secretRef` (Container Apps) or `@Microsoft.KeyVault()` (App Service). ⛔ **Container Apps:** KV `secretRef` entries MUST be gated behind `isPlaceholder` — Phase 1 deploys with `secrets: []`. See [bicep-container-apps.md](bicep-container-apps.md) § Two-Phase Wiring.

### Step 7 — Generate all files

> ⛔ **Before writing ANY file, verify:** (1) KV uses `enableRbacAuthorization: true`, NO `enablePurgeProtection`, NO access policies. (2) No secrets in module outputs — secrets flow through KV only. (3) API versions from `apiVersions` input, not memory. (4) Container Apps: no `revisionSuffix`, placeholder image as default, `isPlaceholder` conditionals on registries/secrets.

**Do:** Create the `infra/` directory and write all files:
1. `infra/bicepconfig.json` — write `{ "formatting": { "newlineKind": "LF" } }` if it doesn't already exist (user's repo may have one). LF is critical because Bicep triple-quoted strings pass content literally to ARM, and `\r` bytes crash `/bin/sh` in containers.
2. `infra/main.bicep` — subscription scope, RG creation with tags, module calls for all services + `role-assignments` module (KV deployer + app-to-KV RBAC), all unconditional.
3. `infra/main.parameters.json` — ARM JSON format (NOT `.bicepparam`). Include `environmentName`, `location`, `sessionId`, `deployedBy`, `createdAt`. ⛔ **`createdAt` value:** run `Get-Date -Format "o"` in terminal to get the current ISO 8601 timestamp — NEVER use a hardcoded or placeholder date. Do NOT include `@secure()` params (passed at deploy time). Include `deployerObjectId` param (deploy phase passes via `az ad signed-in-user show --query id -o tsv`).
4. `infra/modules/{service}.bicep` — one module per service from the plan, PLUS `role-assignments.bicep` (KV Secrets Officer for deployer, KV Secrets User for app identity if MI enabled — see [bicep-patterns-security.md](bicep-patterns-security.md) § Key Vault Deployer RBAC).
5. If `buildRequirements.hasBuildKitSyntax == true`: ⛔ create `{component}/Dockerfile.azure` per [dockerfile-generation.md § ACR Build Compatibility](dockerfile-generation.md).
6. If Container Apps and component has NO Dockerfile: read [dockerfile-generation.md](dockerfile-generation.md) and generate one. Follow the layer ordering, port alignment, and security defaults from that reference — do NOT generate from memory.

> ⛔ **Health probes for Container Apps:** Probe path priority: (1) `prereq-output.json.healthEndpoint` if non-null, (2) first detected GET route from the app, (3) `/` only if the app has a root handler. Do NOT default to `/` for APIs that only serve sub-paths — returns 404, blocks activation. For DB apps: use `/healthz` not `/readyz` (DB not wired in Phase 1).

### Step 8 — Validate syntax

**Do:** Run `az bicep build --file infra/main.bicep --stdout > $null`. If errors, fix and re-run (max 2 attempts). Do NOT use the `azure-validate` skill.

### Step 9 — Return results

**Do:** Return the list of generated files and any validation notes to the caller. Keep status report ≤1500 tokens.
