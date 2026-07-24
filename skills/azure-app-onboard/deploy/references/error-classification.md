# Error Classification

Three error categories for deploy-time failures.

## Multi-Error Triage

> ⛔ When 3+ errors, classify ALL before fixing ANY. Group by root cause. Present: "Deploy failed with {N} errors from {M} root causes."

## Categories

### `IAC_ERROR` — Route Back to Scaffold

| Example | Fix |
|---------|-----|
| Invalid property name | Call `mcp_bicep_build_bicep` with `{ filePath: "infra/main.bicep" }` for structured error details, then fix. Fallback: `az bicep build` |
| Wrong SKU for region | Substitute from `rejectedAlternatives[]` |
| Missing required field | Call `mcp_bicep_build_bicep` for structured error, fix from diagnostics. Fallback: `az bicep build` |
| Policy violation | Substitute per policy |
| API version not found | Call `mcp_bicep_list_az_resource_types_for_provider` with `{ providerNamespace: "..." }`. Use latest GA — no `-preview`. Fallback: `az provider show` |
| `listKeys()` in output | ⛔ Security risk — replace with KV secret + MI reference |
| KV soft-delete collision | Rename KV (append suffix). If not viable → user purges manually |
| Redis `InvalidRequestBody` for `properties.sku.name` | Bicep type issue — create via `az redis create --sku Basic --vm-size c0`, switch Bicep to `existing` keyword |

**Flow:** Deploy → classifies IAC_ERROR → scaffold self-healing → re-validate → retry.

### `INFRA_TRANSIENT` — Retry with Backoff

| Example | Strategy |
|---------|----------|
| ARM 429, 409 conflict, RBAC delay, network timeout | 30s → 60s → 120s (3 max) |
| Container Apps `Operation expired` | Check root cause first: image pull failure, port mismatch, health probe timeout, crash loop. Port mismatch → IAC_ERROR. Image pull → retry. Crash → ENVIRONMENT_BLOCKING. |

After 3 failures → escalate to user.

### `ENVIRONMENT_BLOCKING` — Surface to User

| Example | Action |
|---------|--------|
| 403 on sub-scope deploy | ⛔ Try [403 Scope Fallback](deploy-safety.md) first (RG-scope). Only block if retry also fails |
| 403 on RG-scope | Surface: `az role assignment create --role Contributor --assignee {objectId} --scope {rg}` |
| AuthorizationFailed / deny assignment | Get user objectId, suggest role assignment command. Deny assignments → contact admin |
| Quota exhausted | ⛔ PLAN_LEVEL_CHANGE — HALT, present region fallback with re-approval |
| Region doesn't support resource | ⛔ PLAN_LEVEL_CHANGE — same as quota |
| `LocationIsOfferRestricted` | ⛔ PLAN_LEVEL_CHANGE — read `quotaValidation.offerRestrictions[]` for unblocked regions |
| MI sidecar OOM on F1/B1 | Upgrade SKU, remove MI, or switch to Container Apps |
| AADSTS530084 / TF auth failure | Re-scaffold as Bicep + `az deployment group create`. Never fall back to imperative CLI |

> ⛔ **During ALL healing: NEVER run `az group delete`, `az postgres flexible-server delete`, `az redis delete`, `az webapp delete`, or any destructive resource deletion.** Track failed RGs in `deploy-result.json.orphanedResourceGroups[]` instead. The user deletes at handoff. If you need a clean region retry, use a NEW RG name (append `-2`) — do NOT delete-and-recreate.

## Healing Trace

Log to `deploy-result.json.healingAttempts[]`: `{ attempt, phase, errors: [{ source, detail, classification }], action, result, planLevelChange, changeType, originalValue, newValue }`.

> ⛔ **Repeat failure (same error 2+):** Read [iac-resources.md](../../references/iac-resources.md) § Deploy Troubleshooting and `fetch_webpage` the matching URL.

After 3 failed cycles: write `partial: true`, surface remaining errors. Do NOT auto-rollback.

## Known Platform Bugs / Deploy Timing

See [`pipeline-rules-runtime.md`](../../references/pipeline-rules-runtime.md).
