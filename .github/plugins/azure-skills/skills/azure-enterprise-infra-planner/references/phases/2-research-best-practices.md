# Phase 2: Research WAF

> The goal of this phase is to understand user intent and gather WAF guidance using MCP tools.

## Step 1 - Clarify Requirements

Clarify the user's requirements until you can confidently describe what they want to build. Do NOT proceed to Step 2 until all critical gaps are resolved. Stay focused on *what* the user needs — do not make architectural decisions or propose specific services yet.

1. Extract what's explicitly stated in the user's prompt: workload purpose, traffic expectations, data storage needs, security requirements, and budget constraints.
2. Identify gaps across: workload purpose, data/storage needs, networking requirements, security/compliance constraints, availability expectations, environments, expected scale, and budget. A gap is **critical** if it would fundamentally change the scope of the infrastructure.
3. Ask the user focused questions (≤5 per round) for critical gaps only. Repeat until no critical gaps remain. Defer region and SKU related questions until insights have been generated; only ask the user directly if the insights do not address them.
4. Summarize your understanding of the user's requirements and wait for confirmation before proceeding.

## Step 2 - Identify Sub-Goals

Derive sub-goals and include them in `inputs.subGoals`. Sub-goals are implicit constraints the user hasn't stated but the workload clearly requires. Examples:

- "assume all defaults" -> Cost-optimized: consumption/serverless tiers, minimal complexity.
- "production system" -> Production-grade: zone redundancy, private networking, managed identity.
- "secure" -> Security-first: no public IPs on workload VMs; Bastion + Key Vault SSH key; Trusted Launch; managed identity over keys.
- "observable" -> Operational excellence baseline: Log Analytics + VM Insights, NSG flow logs, boot diagnostics, NAT Gateway for deterministic egress.

## Step 3 - Research WAF

> Mandatory: Call WAF MCP tools before reading local resource files.

1. Call `get_azure_bestpractices` with `resource: "general"`, `action: "all"` for baseline guidance. Call once only.
2. Call `wellarchitectedframework_serviceguide_get` with `service: "<name>"` **for each** core service (in parallel). Examples: `"Container Apps"`, `"Cosmos DB"`, `"App Service"`, `"Event Grid"`, `"Key Vault"`. Return URLs only.
3. Dispatch sub-agents in parallel to fetch **every** WAF URL (never inline — guides are 20–60 KB) and summarize in ≤500 tokens. Focus on: additional resources needed, required properties for security and reliability, and key design decisions. Do not skip this step to keep token usage down, even if the core WAF principles for these services are already well-established and captured in your plan.
4. Collect all WAF findings: missing resources, property hardening, architecture patterns.

## Gate

- All tool calls must be completed and all WAF guides summarized.
