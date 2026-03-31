# Research Phase

Research is sequential: identify resources → call WAF tools → refine → load resource files.

## Input Analysis

| Scenario | Action |
|----------|--------|
| Repository | Scan `package.json`, `requirements.txt`, `Dockerfile`, `*.csproj` for runtime/dependencies. |
| User requirements | Clarify workload purpose, traffic, data storage, security, budget. |
| Multi-environment | Ask about dev/staging/prod sizing differences. |

## Step 1 — Identify Core Resources and Sub-Goals

From the user's description, list the core Azure services (compute, data, networking, messaging). Also derive sub-goals — implicit constraints to include in `inputs.subGoals`:
- "assume all defaults" → `"Cost-optimized: consumption/serverless tiers, minimal complexity"`
- production system → `"Production-grade: zone redundancy, private networking, managed identity"`

## Step 2 — WAF Tool Calls

> Mandatory: Call WAF MCP tools before reading local resource files. Complete this step before proceeding.

1. Call `get_azure_bestpractices` with `resource: "general"`, `action: "all"` for baseline guidance.
2. Call `wellarchitectedframework_serviceguide_get` with `service: "<name>"` for each core service (in parallel). Examples: `"Container Apps"`, `"Cosmos DB"`, `"App Service"`, `"Event Grid"`, `"Key Vault"`.
3. The tool returns a markdown URL. Use a sub-agent to fetch and summarize in ≤500 tokens, focusing on: additional resources needed, required properties for security/reliability, key design decisions.
4. Collect all WAF findings: missing resources, property hardening, architecture patterns.

## Step 3 — Resource Refinement

> Mandatory: Walk through the WAF checklist and document what was added or intentionally omitted.

Walk through every concern in the [WAF cross-cutting checklist](waf-checklist.md) and add missing resources or harden properties. For each checklist item, either add the resource/property or document the intentional omission in `overallReasoning.tradeoffs` and `inputs.subGoals`. Present the refinement summary to the user before proceeding to Step 4.

## Step 4 — Resource Lookup via Tools

> Mandatory: Complete this step for every resource before generating the plan. WAF tools (Step 2) provide architecture guidance but do not provide ARM types, naming rules, or pairing constraints. This step fills those gaps. Read [resources/README.md](resources/README.md) to identify which category files contain the resources you need, then load only those category files.

For each resource identified in Steps 1-3:

1. Look up the resource in the relevant [resources/](resources/README.md) category file (e.g., `resources/compute-infra.md` for AKS, `resources/data-analytics.md` for Cosmos DB) to get its ARM type, API version, and CAF prefix. Read the index in `resources/README.md` to find the right category file.
2. Use a sub-agent to call `microsoft_docs_fetch` with the naming rules URL from the resource category file. Instruct the sub-agent: "Extract naming rules for {service}: min/max length, allowed characters, uniqueness scope. ≤200 tokens." Fall back to `microsoft_docs_search` with `"<resource-name> naming rules"` only if the URL is missing or returns an error.
3. Read pairing constraints for the resource from the matching [constraints/](constraints/README.md) category file (e.g., `constraints/networking-core.md` for VNet, `constraints/security.md` for Key Vault). Each category file is <2K tokens — read the whole file for all resources in that category.

   Use the [constraints/README.md](constraints/README.md) index to find the right category file for each resource name.

> Important: Only load the category files you need. For a plan with AKS + Cosmos DB + VNet + Key Vault, you'd load 4 constraint files and 4 resource files (~5,500 tokens total) instead of the full catalog (~21,600 tokens).

From the tool results, verify:

1. Type — Correct `Microsoft.*` resource type and API version
2. SKU — Available in target region, appropriate for workload
3. Region — Service available, data residency met
4. Name — CAF-compliant naming constraints
5. Dependencies — All prerequisites identified and ordered
6. Properties — Required properties per resource schema
7. Alternatives — At least one alternative with tradeoff documented
