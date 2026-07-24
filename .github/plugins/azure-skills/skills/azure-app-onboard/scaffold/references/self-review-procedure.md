# Self-Review Procedure — Step 9

Adversarial self-review using a sub-agent to perform L1–L4 review of generated IaC.

## Sub-Agent Setup

Use a sub-agent to perform the review. Provide:
- All generated IaC file contents (every .bicep or .tf file from Step 5)
- The `prepare-plan.json` services/naming/deploymentVariables sections
- The `scaffold-manifest.json.files[]` list
- The full content of [self-review-checklist.md](self-review-checklist.md) AND [waf-checklist.md](waf-checklist.md) verbatim

## Sub-Agent Prompt

> "Follow the self-review-checklist.md procedures for EACH of L1–L4. Rate each finding as VERIFIED | PLAUSIBLE | FLAGGED. Check: L1 Security (RBAC scope, network rules, managed identity, Key Vault — check contradictions between IaC and plan), L2 Pattern (anti-patterns, missing supporting resources — verify every file in scaffold-manifest.json.files[] exists on disk and is non-empty, FLAGGED if any missing or empty), L3 Hallucination (resource names match prepare-plan.json.naming exactly, API versions are real, SKU names match plan, no invented resource types), L4 WAF (use waf-checklist.md — Reliability, Security, Cost, Ops, Performance per-service checks). Do not fabricate results — check each claim against the actual IaC content provided. Return: { findings: [{ layer: 'L1'|'L2'|'L3'|'L4', claim: '...', rating: 'VERIFIED'|'PLAUSIBLE'|'FLAGGED', detail: '...' }], summary: 'N/N VERIFIED, N PLAUSIBLE, N FLAGGED' }. ≤1000 tokens."

## Consume Results

- If any finding is FLAGGED → fix the IaC, then re-run validation (`az bicep build`, `az deployment sub what-if`)
- If all VERIFIED/PLAUSIBLE → proceed to Step 10
- Write findings to `scaffold-manifest.json.selfReview`

> ⛔ **Self-review is COMPLETE after L1–L4.** L3 may use `mcp_bicep_get_bicep_file_diagnostics`, `az bicep build`, or `az deployment sub what-if` — all are appropriate for catching errors early. **Step 12 remains mandatory regardless of what self-review found** — IaC may change between Steps 9–12 (FLAGGED fixes), and Step 12 writes the contractual `validationResult` to the manifest.

> ⛔ **Halt on critical self-review failures** — if any selfReview finding is FLAGGED at L1 (Security) or L3 (Hallucination), do NOT proceed to deploy. Present findings and ask: **"Fix / Continue with risks / Cancel"**.
