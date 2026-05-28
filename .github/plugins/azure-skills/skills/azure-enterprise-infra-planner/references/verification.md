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

Read [pairing-checks.md](pairing-checks.md) in full. It covers SKU compatibility, subnet/network conflicts, storage pairing, Cosmos DB, Key Vault/CMK, SQL Database, and AKS networking. For every connected pair of resources in the plan, walk through each applicable rule, confirm compliance, and fix any violation in-place before moving on to the next pair.

## 4. Insights Checks

Skip this section when `insights.json` does not exist or contains no insights.

| # | Check | Fix |
|---|-------|-----|
| 1 | Every insight in `insights.json` is either justified in `inputs.insightsApplied` or has a documented reason for non-application in `plan.overallReasoning.tradeoffs`. An insight must not appear in both. | Add the insight to `insightsApplied` or document why it was not followed. |
| 2 | Every entry in `inputs.insightsApplied` cites the insight ID correctly, and its description of how and why it was applied references the insight's pattern and planning implication. | Correct the entry or remove it if it was applied incorrectly. |
| 3 | No insight should result in a weaker security posture than available alternatives, unless it is explicitly requested in the user prompt or stated in the sub-goals. | Revert to the stronger alternative and move the insight to `plan.overallReasoning.tradeoffs` with an explanation. |
