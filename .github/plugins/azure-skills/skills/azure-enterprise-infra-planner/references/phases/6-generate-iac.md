# Phase 6: Generate IaC

> Important: Before continuing this phase, `meta.status` must be set to `approved` as required by Phase 5.

1. Ask the user whether to generate Bicep or Terraform.
2. Generate IaC from the approved plan. Refer to [bicep-generation.md](../bicep-generation.md) for Bicep or [terraform-generation.md](../terraform-generation.md) for Terraform.
3. **Apply secure-by-default (mandatory).** Unless the approved plan explicitly overrides a control, every generated resource must use:
   - Private endpoints and `publicNetworkAccess: Disabled` on data/PaaS services — no unnecessary public exposure.
   - Managed identity + RBAC instead of keys/connection strings; no secrets in code (`@secure()` / `sensitive = true`).
   - Storage `allowSharedKeyAccess: false`; Key Vault soft-delete + purge protection; AKS managed identity with local accounts disabled.
   - Minimum TLS 1.2 and encryption in transit.
4. **Validate, security-scan, and fix until clean (mandatory, self-verifying).** No-deploy, purely local:
   - **Bicep:** run `az bicep build --file infra/main.bicep`.
   - **Terraform:** run `terraform init -backend=false` then `terraform validate` in `infra/`.
   - **Security scan:** run `checkov -d infra/` and resolve every high/critical finding.
   - If any command reports errors or unresolved high/critical findings, fix the files in-place and re-run. Repeat until every command exits cleanly.
   - **Prove it:** paste the exact command(s) run and their final exit status / summary into your response. Do not claim the gate passed without showing the output. If a tool is genuinely unavailable, say so explicitly and self-review against the generation correctness checklist and the secure-by-default list above.
5. **Emit the completion self-check.** End Phase 6 with this checklist, each line marked pass/fail with a one-line reason:
   - [ ] Validation ran and exited clean (output shown)
   - [ ] `checkov` ran; no unresolved high/critical findings
   - [ ] Secure-by-default applied (private endpoints, MI/RBAC, TLS 1.2, no secrets)
   - [ ] Referenced resources wired, none recreated (referenced mode only)
   - [ ] Files under `infra/`; original source artifacts untouched

## Gate
- All required IaC files generated and saved to disk under `<project-root>/infra/`.
- `az bicep build` (Bicep) or `terraform validate` (Terraform) **and** `checkov` complete with zero errors and no unresolved high/critical findings, **with the command output shown in the response**.
- The completion self-check is emitted with every item passing (or an explicit, justified exception).
