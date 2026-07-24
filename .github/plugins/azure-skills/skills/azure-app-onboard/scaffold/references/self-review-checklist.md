# Self-Review Checklist

4-layer adversarial review of generated IaC. Run after scaffold generates all files, before `scaffold-manifest.json`.

## Rating System

- **VERIFIED** — confirmed correct by inspecting the generated code
- **PLAUSIBLE** — likely correct but cannot fully verify (e.g., API version exists but not checked against registry)
- **FLAGGED** — incorrect, missing, or contradicts the plan/patterns

**Consume results:** If any finding is FLAGGED → fix the IaC, then re-run validation. If all VERIFIED/PLAUSIBLE → proceed. Write findings to `scaffold-manifest.json.selfReview`.

> ⛔ **Halt on critical failures** — if any finding is FLAGGED at L1 (Security) or L3 (Hallucination), do NOT proceed to deploy. Present findings and ask: **"Fix / Continue with risks / Cancel"**.

> ⛔ **Step 12 validation remains mandatory** regardless of self-review results — IaC may change during FLAGGED fixes.

## Layer 1 — Security Claims Extraction

Extract every security claim from the generated IaC and check for internal contradictions.

| Check | Example |
|-------|---------|
| Managed identity declared but secret hardcoded | `identity: { type: 'SystemAssigned' }` but `password: 'hardcoded'` in same file |
| HTTPS enforced but HTTP endpoint exposed | `httpsOnly: true` but ingress allows HTTP |
| Resource accessed via managed identity but matching role not granted | KV secret read without KV Secrets User, ACR image pull without AcrPull, or any MI→resource dependency missing its `roleAssignment` — access fails at runtime → `FLAGGED` |
| ⛔ Role assignment scope targets wrong resource | `scope: resourceGroup()` on resource-specific roles → `FLAGGED`. Must scope to specific resource. |
| `principalType` missing on role assignments | Causes intermittent 30s+ delays |
| ⛔ Identity block missing on compute resource | ⛔ **MANDATORY FAIL** — ALL compute MUST have `identity: { type: 'SystemAssigned' }`. ⛔ **HARD EXCEPTION — F1/D1 Linux:** MI sidecar causes OOM on free tier → rate `PLAUSIBLE`, **NEVER** `FLAGGED`. The gen template intentionally omits MI for F1/D1. If F1/D1 detected in plan, this check MUST be `PLAUSIBLE`. |
| SQL firewall `0.0.0.0/0` without private endpoint | Prefer MI + private endpoint. AllowAzureServices genuinely needed → `PLAUSIBLE`. |
| ⛔ SCM/FTP auth policy missing on App Service | ALL App Service MUST have `basicPublishingCredentialsPolicies`: `scm.allow: true`, `ftp.allow: false`. Missing → `FLAGGED`. |
| ⛔ KV URL uses `environment().suffixes.keyvaultDns` | Leading dot → double-dot URL → `ContainerAppSecretKeyVaultUrlInvalid`. Use `keyVault.name` + `.vault.azure.net` or `vaultUri` output. → ⛔ **FLAGGED** |

**Rating:** Claims that contradict each other → `FLAGGED`. Consistent claims → `VERIFIED`.

## Layer 2 — Pattern Validation

Validate against pattern files loaded at Steps 3–5 and [rbac-roles.md](rbac-roles.md).

### Bicep

| Check | Source |
|-------|--------|
| File structure: `main.bicep` → `modules/*.bicep` | `bicep-patterns.md` |
| `main.parameters.json` uses ARM JSON (not `.bicepparam`) | `bicep-patterns.md` |
| Naming: `{prefix}{name}{token}` ≤32 chars | `bicep-patterns.md` |
| System-assigned managed identity on all services | `bicep-patterns-security.md` |
| No `administratorLogin` in generated Bicep | `bicep-patterns-security.md` |
| KV uses RBAC authorization (not access policies) | `bicep-patterns-security.md` |
| ⛔ `enablePurgeProtection` exists in KV module | Remove — `false` rejected by ARM, `true` blocks KV deletion → ⛔ **FLAGGED** |
| ⛔ KV deployer role assignment — `Key Vault Secrets Officer` for `deployerObjectId` scoped to KV resource | `bicep-patterns-security.md` § Key Vault Deployer RBAC. Without this, `az keyvault secret set` fails with 403. |
| Prereq `warnings[]` each have a corresponding IaC fix | Read [`env-var-secrets.md`](env-var-secrets.md) for SSL/TLS fixes |
| Container Apps: two-phase ACR wiring, `registries` populated when ACR in plan, port alignment | `bicep-container-apps.md` |
| ⛔ BuildKit Dockerfile without `Dockerfile.azure` | `hasBuildKitSyntax == true` but no `Dockerfile.azure` in `files[]` → ⛔ **MANDATORY FAIL**. ACR does not support BuildKit. |
| ⛔ Role assignment `scope` targets specific resource, not `resourceGroup()` | `rbac-roles.md` |
| ⛔ No `azure.yaml` in `scaffold-manifest.json.files[]` | `pipeline-rules.md` |
| Non-Azure TF in separate dir | `terraform-patterns.md` |

### Cross-Module Reference Validation

Trace references BETWEEN modules — per-file checks miss broken cross-module wiring.

| Check | Rating |
|-------|--------|
| **Param wiring** — every `module` call in `main.bicep`: verify every param without `= default` is passed | Missing param → `FLAGGED` |
| **Secret ref completeness** — every CA `secrets[].keyVaultUrl` has a matching KV secret resource | Missing KV secret → `FLAGGED` |
| **Output ref validity** — every `moduleRef.outputs.X` is declared in the referenced module | Missing output → `FLAGGED` |

### Terraform

| Check | Source |
|-------|--------|
| File structure: `main.tf`, `variables.tf`, `outputs.tf`, `backend.tf`, `modules/` | `mcp_azure_mcp_azureterraformbestpractices` |
| Provider: `azurerm ~> 4.0` | Terraform registry |
| System-assigned managed identity, no `administrator_login`, KV RBAC | `terraform-patterns.md` |
| Container Apps: two-phase ACR wiring | Same pattern as Bicep |

**Rating:** Matches → `VERIFIED`. Reasonable deviation → `PLAUSIBLE`. Violates → `FLAGGED`.

## Layer 3 — Hallucination Detection

Catch fabricated resource types, API versions, SKU names, or properties.

### Bicep (default path)

| Check | How |
|-------|-----|
| API versions, resource types, property names valid | `bicep build` — errors = `FLAGGED` |
| ⛔ Deploy-time value validity (`bicep build` blind spot) | The compiler accepts any schema-valid string, but ARM rejects wrong enum-like values (engine versions, region-restricted SKUs), wrong resource `scope`, and empty resource-ID properties. Any such value the generator chose from memory — not traceable to `prepare-plan.json` or a pattern file — MUST be confirmed against the provider capabilities API; unconfirmed → `FLAGGED`. |
| SKU names match `prepare-plan.json` | Cross-reference `services[].sku` |
| OpenAI deployment uses `scaleSettings` instead of `sku` | `scaleSettings` deprecated → `FLAGGED` |
| Any resource uses `-preview` API version | Use latest GA from MCP tool → `FLAGGED` |
| VNet subnets as separate child resources | Must be inline in `properties.subnets[]` → `FLAGGED` |

Run `bicep build main.bicep --stdout > /dev/null` as syntax + schema validation. Parse errors = `FLAGGED`.

> ⛔ **`az bicep build` is MANDATORY for L3.** If unavailable, write `FLAGGED` with "bicep build unavailable."

> ⛔ **Verify `main.bicep` has `targetScope = 'subscription'`.** Missing → FLAGGED (FIXABLE — add targetScope, RG resource with tags, `scope: rg` on modules).

> `mcp_bicep_build_bicep` + `az deployment sub what-if` also appropriate at L3. ⛔ Do NOT use `az deployment sub validate` (known bug).

**Rating:** Passes `bicep build` → `VERIFIED`. Build warning → `PLAUSIBLE`. Build error → `FLAGGED`.

### Terraform (alternative path)

Run `terraform init -backend=false && terraform validate` + `terraform plan -detailed-exitcode`. Same rating criteria as Bicep.

**Rating:** Passes validate + plan → `VERIFIED`. Plan warning → `PLAUSIBLE`. Validate/plan error → `FLAGGED`.

## Layer 4 — WAF Alignment

Per-pillar spot check against [Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/).

| Pillar | Check |
|--------|-------|
| Reliability | Health probes configured. ⛔ Verify probe path matches `prereq-output.json.healthEndpoint` — non-existent or mismatched path = `FLAGGED`. ⛔ ACA probes do NOT follow HTTP redirects — if app has trailing-slash normalization (Express `redirect`), use path WITHOUT trailing `/` (e.g., `/app` not `/app/`). |
| Security | No public blob access, TLS 1.2+, managed identity |
| Cost | SKU matches budget tier from `prepare-plan.json` |
| Ops | App Insights present + connected for APM, 5 AppOnboard tags on resources, all values parameterized. Present = `VERIFIED`. App Insights absent = `PLAUSIBLE`. ⛔ `diagnostic-settings` is not part of the plan — if the generator added one it MUST be gated (`if (enableDiagnostics)`, default `false`) or absent; wired UNCONDITIONALLY in `main.bicep` = `FLAGGED` (blocks first deploy). |
| Performance | Autoscale rules present for production SKUs |
| Reliability | ⛔ Env var values compatible with app config validation (Pydantic `Settings`, Django `settings.py`). Typed fields reject wrong formats → `FLAGGED` |

**Rating:** Pillar addressed → `VERIFIED`. Not applicable for SKU → `PLAUSIBLE`. Missing for production SKU → `FLAGGED`.

## Output

Write findings to `scaffold-manifest.json.selfReview.findings[]`: `{ "layer": "L1", "claim": "...", "rating": "FLAGGED", "detail": "..." }` (layer is one of `"L1"`|`"L2"`|`"L3"`|`"L4"`). All `FLAGGED` must be resolved or surfaced at deploy gate. `PLAUSIBLE` = informational.
