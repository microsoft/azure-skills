# Phase 7: Deployment

## Destructive Action Gate

This phase is destructive and has irreversible effects. Explicitly confirm with the user whether to deploy, and mention the risks of altering live environments. Never accept implicit or vague intent; only continue if the user acknowledges the risks and instructs you to proceed (e.g. "I understand the risks, continue with deployment") in a reply sent *after* you have presented the risks. The original task prompt never satisfies this gate, even if it says "deploy" or "run all phases". Stop if no such reply is received. Do not accept vague statements such as "continue", "yes", "deploy now" (without risk acknowledgement), or "go ahead".

---

> Important: Before continuing this phase, `meta.status` must be set to `approved` as required by Phase 5. Each destructive action requires explicit user confirmation.

Refer to [deployment.md](../deployment.md) for executing deployment commands.

1. Confirm subscription and resource group with user
2. Select the correct deployment scope based on `targetScope` in `main.bicep` (resource group, subscription, management group, or tenant)
3. Run `az bicep build` to validate, then execute the matching scope command (`az deployment group create`, `az deployment sub create`, etc.) or `terraform apply`
