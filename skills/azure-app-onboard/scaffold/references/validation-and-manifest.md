# Validation, Manifest & Approval — Steps 10–12.5

## Step 10 — CI/CD

Do NOT auto-generate workflow files or create branches/PRs. Scaffold only writes IaC files. This step activates only when `context.json.repo.remote` is non-null AND user explicitly requests branch/PR creation. When `repo.remote` is absent or user declines, write IaC directly to working tree. If the user asks for CI/CD, or after deploy completes, suggest it as a follow-up: call `mcp_azure_mcp_deploy` → `deploy_pipeline_guidance_get` with `is-azd-project: false`, `pipeline-platform: "github-actions"`, `deploy-option: "provision-and-deploy"` and present the guidance for the user to apply.

## Step 11 — Validate Generated IaC

> ⛔ **Validation MUST happen BEFORE the manifest is written.** The manifest requires `validationResult` — you cannot write it without completing validation first. Do NOT write `scaffold-manifest.json` until validation has run.

> ⛔ Do NOT call other skills during scaffold/deploy — see [pipeline-rules.md](../../references/pipeline-rules.md).

Run these checks directly. All must pass.

**11a. Bicep compilation:**
```powershell
az bicep build --file infra/main.bicep --stdout > $null
```
(Bash: redirect to `/dev/null` instead of `$null`.) Pass: exit 0. Fail: fix errors and retry.

**11b. Static RBAC review** — review generated Bicep for correct role assignments per [rbac-roles.md](rbac-roles.md). Every managed identity ↔ resource pair must have a `Microsoft.Authorization/roleAssignments` resource with the correct role GUID.

**11c. Write `validationResult`** — after all checks pass, write:
```json
{
  "validationResult": {
    "status": "Validated",
    "checks": [
      { "name": "bicep build", "result": "PASS" },
      { "name": "RBAC review", "result": "PASS" }
    ]
  }
}
```

**Terraform path:** Replace 11a with `terraform init -backend=false && terraform validate`.

- If validation finds FIXABLE errors: edit IaC → re-run self-review (L1–L4) → re-validate (max 3 attempts). ⛔ **You MUST read [scaffold-healing-rules.md](scaffold-healing-rules.md) before entering the healing loop** — it defines error classification (FIXABLE vs BLOCKING) and auto-fix strategies.
- If BLOCKING errors remain after 3 attempts: surface to user and halt.

## Step 12 — Write `scaffold-manifest.json`

⛔ **You MUST read [`scaffold-schemas.ts`](scaffold-schemas.ts)** to get the exact `ScaffoldManifest` interface. Write to the session folder with ALL fields populated: `files[]`, `selfReview.findings[]`, AND `validationResult` (from Step 11). This is a single write — validation is already complete.

> ⛔ **Phase exit gate: `scaffold-manifest.json.validationResult` MUST NOT be null.** If validation ran: `{ status: 'Validated'/'Partial'/'Failed', details }` (per `ValidationResult` in [`scaffold-schemas.ts`](scaffold-schemas.ts)). Null = incomplete scaffold.

**You MUST also update `context.json`** per `AppOnboardContext` in [`session-schemas.ts`](../../references/session-schemas.ts): append `"scaffold"` to `completedPhases`, set `currentPhase` to `"deploy"`, update `lastModifiedUtc`.

## Step 12.5 — Deploy Approval Gate

Present the user with: files generated, selfReview findings, **validation results** (pass/fail per check from Step 11), services + SKUs, secure-defaults applied. End with: **"Ready to deploy? (Yes / Run manually / Edit plan / Cancel)"** — do not continue until the user approves.

> ⛔ **Self-check before presenting the deploy gate.** Does `scaffold-manifest.json` contain a `validationResult` field with `status` set? If NO → you skipped Step 11. Go back and run validation. Do NOT present the deploy gate with `validationResult: null`.

> ⛔ **Quota gate — MANDATORY.** Read `prepare-plan.json.quotaValidation`. If `verified == false`, `method == "unverifiable"`, or `method` is not `"cli"` for quota-constrained services: read [`sku-quota-validation.md`](../../prepare/references/sku-quota-validation.md) § Deploy Gate Re-Validation and follow the procedure.
> ⛔ Do NOT use `az vm list-usage`, `az appservice list-locations`, or `mcp_azure_mcp_quota` for quota checks — see Anti-Patterns in [`sku-quota-validation.md`](../../prepare/references/sku-quota-validation.md).


> ⛔ **Azure service compatibility warnings.** Read `prereq-output.json.warnings[]` for any warnings with `fixPhase: "deploy-gate"`. Surface EACH at the deploy gate: "⚠️ Azure compatibility: {warning.summary}. Fix: {warning.fix}. Approve? (Yes / Skip / Cancel)". If the user skips, add to `postDeployRecommendations[]`.

> ⛔ **Phase exit — NOT complete until ALL done:**
> 1. `scaffold-manifest.json` written with `files[]`, `selfReview.findings[]`, AND `validationResult`
> 2. `context.json`: `"scaffold"` appended to `completedPhases`, `currentPhase` → `"deploy"`, `lastModifiedUtc` updated
> 3. `deploy-checklist.md` exists in session folder — written by the parallel checklist subagent at scaffold Step 5b (before IaC gen completes). Verify it exists. If missing (subagent failed), write it now from [`deploy-checklist-template.md`](../../deploy/references/deploy-checklist-template.md) — fill in real values from `prepare-plan.json`, delete unrelated compute sections.
