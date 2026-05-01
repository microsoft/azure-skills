# Scaffold & Parameterize

Use this reference to fetch the confirmed template and wire up parameters.

## Path A — OFFICIAL / ADAPT

If the user has no GitHub access, the template must already be present in the workspace. Do NOT attempt to fetch from GitHub.

Fetch the template from the GitHub URL in [template-index.md](template-index.md). Choose **Bicep or Terraform** based on the user's preference or existing workspace files. Fetch the **entire template folder** including subdirectories. Create the files in the user's workspace (e.g., `infra/` folder).

For ADAPT: after fetching, modify the template to match the user's requirements before parameterizing.

## Path B — EXTEND

If the user has existing Bicep or Terraform templates they want to extend, load [custom-template-adaptation.md](custom-template-adaptation.md). Follow the gap analysis there: read the user's template, identify what's present, add only the missing mandatory resources.

Set parameter values using the answers collected in [intake.md](intake.md):

| Parameter | Source |
|-----------|--------|
| Location | Region (or inferred from existing VNet) |
| VNet name / resource ID | VNet answer (new or existing) |
| VNet address space | Address space from requirements (default `192.168.0.0/16`) |
| Subnet CIDRs | Subnet answers (agent `/24`, PE `/24`, MCP `/24` if needed) |
| Existing Cosmos DB / Storage / AI Search IDs | BYO resource IDs (only if reusing) |
| Isolation mode (T18 only) | Managed VNet outbound mode (`AllowOnlyApprovedOutbound` or `AllowInternetOutbound`) |
| Model name, version, format | Model selection from requirements |
| `disableLocalAuth` | Set `true` if Azure Policy requires it |

> Do NOT run `az deployment group create` yet — validate first (next step).
