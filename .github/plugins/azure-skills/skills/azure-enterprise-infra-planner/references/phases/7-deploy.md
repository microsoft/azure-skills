# Phase 7: Deployment

> Important: Before continuing this phase, `meta.status` must be set to `approved` as required by Phase 5. Destructive actions require explicit user confirmation.

Refer to [deployment.md](../deployment.md) for executing deployment commands.

1. Confirm subscription and resource group with user
2. Select the correct deployment scope based on `targetScope` in `main.bicep` (resource group, subscription, management group, or tenant)
3. Run `az bicep build` to validate, then execute the matching scope command (`az deployment group create`, `az deployment sub create`, etc.) or `terraform apply`
