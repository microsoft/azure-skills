# Resource Verification

Run these checks immediately after writing each resource to `plan.resources[]`. Fix issues in-place before moving to the next resource. Load the relevant category file from [resources/](resources/README.md) for naming constraints, valid SKUs, and pairing rules.

## 1. Name Checks

| # | Check | Fix |
|---|-------|-----|
| 1 | Follows CAF pattern from resource file Identity/Naming section | Rewrite using correct abbreviation |
| 2 | Length within min/max for type | Truncate or restructure |
| 3 | Only allowed characters for type | Strip disallowed characters |
| 4 | Globally-unique names avoid collisions | Add distinguishing suffix |
| 5 | Required subnet names exact (`AzureFirewallSubnet`, `GatewaySubnet`, `AzureBastionSubnet`) | Use exact required string |
| 6 | Function Apps sharing Storage diverge within first 32 chars | Rename or separate storage |
| 7 | AKS `MC_{rg}_{cluster}_{region}` ≤ 80 chars | Shorten names |

## 2. Dependency Checks

| # | Check | Fix |
|---|-------|-----|
| 1 | Every `dependencies` entry references an existing resource name in the plan | Add missing resource or remove stale ref |
| 2 | Implicit dependencies are explicit (subnet→VNet, App Service→Plan) | Add missing entries |
| 3 | No circular dependencies | Break weaker edge |

## 3. Property & Pairing Checks

Cross-check against every already-written connected resource. Consult the resource file's Pairing Constraints section and [pairing-checks.md](pairing-checks.md) for full rules covering: SKU compatibility, subnet/network conflicts, storage pairing, Cosmos DB, Key Vault/CMK, SQL Database, and AKS networking.
