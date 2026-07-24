# Error Handling — Scaffold Sub-Skill

| Error | Remediation |
|-------|-------------|
| `prepare-plan.json` missing | Trigger prepare backfill via `azure-app-onboard` orchestrator. Do not generate IaC without a plan. |
| Existing Azure IaC (`.bicep`, `azure.yaml`, or `.tf` with `azurerm` provider) | ⛔ Never delete/overwrite; move to `.copilot-azure/sessions/<id>/replaced-files/` (mirror path), tell the user their original was preserved at that backup location, then scaffold. |
| Existing non-Azure IaC (`.tf` with GCP/AWS provider) | Generate Azure TF alongside — see [terraform-patterns.md § Non-Azure IaC coexistence](terraform-patterns.md). Do NOT halt. |
| MCP tool unavailable | Fall back to reference patterns. Flag generated IaC as "unverified against best practices." |
| Self-review finds FLAGGED items | Include in `scaffold-manifest.json.selfReview.findings[]`. Surface at approval gate. |
| Self-healing exhausted (3 attempts) | Pause auto-healing. Present diagnosis: (1) explain error pattern, (2) propose specific next fix, (3) ask user: "Yes, try that" / "I have a suggestion" / "Stop." If user continues, auto-heal for 5 more, then ask every 5 thereafter. If user stops, write `validationResult` with `status: "Failed"` and all errors. Do NOT proceed to deploy. |
| Schema summary exceeds token limit | Use sub-agent pattern: compress each schema to ≤500 tokens. |
| `context.json` malformed | Halt. Report: "Session state corrupted — consider starting a fresh session." |
