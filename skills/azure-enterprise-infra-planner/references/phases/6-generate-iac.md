# Phase 6: Generate IaC

> Important: Before continuing this phase, `meta.status` must be set to `approved` as required by Phase 5.

1. Ask the user whether to generate Bicep, Terraform, or stop here. Never accept vague statements such as "continue", "yes", "go ahead", "proceed", or "make it". Only continue if the user instructs you to generate IaC and names the flavor (e.g. "yes, generate the Bicep" or "go ahead with Terraform").
2. Generate IaC from the approved plan. Refer to [bicep-generation.md](../bicep-generation.md) for Bicep or [terraform-generation.md](../terraform-generation.md) for Terraform.

## Gate
- All required IaC files generated and saved to disk.
