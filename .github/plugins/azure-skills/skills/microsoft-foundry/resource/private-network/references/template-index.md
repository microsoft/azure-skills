# Template Index — Foundry Private Network

Official templates for deploying Microsoft Foundry. Each template may be available in Bicep, Terraform, or both — use one, not both. Choose based on the user's preference or existing workspace files. Use tools to fetch Bicep and Terraform templates to understand available templates and recognize if any matches user's requirements:

**Bicep templates:** https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/

**Terraform templates:** https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-terraform/

Not all templates exist in both Bicep and Terraform. Some have format-specific variants (e.g., Terraform has `15a`/`15b` for new VNet vs BYO VNet; Bicep has `15a` for evaluation-only).

## How to Use

1. Fetch the **directory listing** from the relevant repo URL above — the folder names are descriptive (e.g., `15-private-network-standard-agent-setup`, `18-managed-virtual-network-preview`)
2. Narrow to 1–2 candidates that match the user's requirements based on folder names
3. Fetch only those candidates' READMEs for full details (prerequisites, parameters, deployment instructions)

> The root README is incomplete — do not rely on it for template discovery. Use the directory listing instead.
