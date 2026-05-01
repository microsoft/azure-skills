---
name: private-network
description: "Answer questions about and deploy Microsoft Foundry with network isolation. Covers BYO VNet, Managed VNet, hybrid patterns, private endpoints, and Bicep deployment. WHEN: 'Foundry networking', 'BYO VNet vs managed VNet', 'deploy Foundry in private VNet', 'private endpoints for Foundry'. DO NOT USE FOR: generic Azure networking without Foundry."
license: MIT
allowed-tools: Read, Write, Bash, AskUserQuestion, microsoft_docs_search, microsoft_docs_fetch
---

# Microsoft Foundry Private Networking

## Quick Reference

| Property | Value |
|----------|-------|
| **Best for** | Foundry with VNet isolation, private endpoints, subnet delegation, APIM + Foundry, VPN/Bastion access |
| **Tools** | Azure CLI |
| **MCP Tools** | `AskUserQuestion` - ask user questions; `microsoft_docs_search` - verify facts before presenting; `microsoft_docs_fetch` - fetch full Learn pages for validation |
| **Workflow** | Ground in Learn → Gather → Plan → Scaffold → Validate → Deploy → Test |

### Key Documentation

| Topic | URL |
|-------|-----|
| Network isolation | https://learn.microsoft.com/azure/ai-foundry/how-to/configure-private-link |
| Agent Service VNet | https://learn.microsoft.com/azure/ai-services/agents/how-to/virtual-networks |
| Managed VNet | https://learn.microsoft.com/azure/ai-foundry/how-to/configure-managed-network |
| Feature limitations | https://learn.microsoft.com/azure/foundry/how-to/configure-private-link#foundry-feature-limitations |

## When to Use

- User asks about Foundry networking, private endpoints, or VNet isolation
- User asks about BYO VNet, Managed VNet, or hybrid patterns
- User wants to deploy Foundry agents in a private network
- User needs APIM integration with private Foundry agents

**Do NOT use for:**
- Public Foundry setup without VNet → use [project/create](../../project/create/create-foundry-project.md)
- Bare Foundry resource without networking → use [resource/create](../create/create-foundry-resource.md)

---

## Step 0 — Ground in Microsoft Learn
Use `microsoft_docs_fetch` to get docs from Key Documentation sources.
Use `microsoft_docs_search` to verify any technical fact before presenting it to the user. If Learn contradicts a reference file, **Learn wins**. Cite the URL. If Learn doesn't cover it, say so — do not invent facts, limits, flags, or compatibility claims.

---

## End-to-End Deployment Workflow

> **Important:** All following steps are mandatory. Communicate the plan with the user before acting.

## Step 1 — Gather Requirements

Read [references/intake.md](references/intake.md). One pass, three tiers:
- **Tier 1 (Core):** Subscription, VNet model, agents, region, RG, VNet — determine approach at the end
- **Tier 2 (Architecture):** DNS, topology, NSG, on-prem, identity, BYO resources
- **Tier 3 (Enterprise):** Model, client access, auth, policies, monitoring

Determine the approach (official template / adapt closest / extend user’s IaC) at the end of Tier 1. Continue through Tiers 2–3.

---

## Step 2 — Plan Generation

Use the confirmed requirements from [references/intake.md](references/intake.md).

**OFFICIAL path:** Load the template's README from its GitHub URL (via [references/template-index.md](references/template-index.md)). Run `microsoft_docs_search` for its prerequisites. Present a deployment plan using the user's actual values.

**ADAPT path:** Load the closest template's README. Present a deployment plan highlighting what will be modified from the base template.

**EXTEND path:** Load [references/custom-template-adaptation.md](references/custom-template-adaptation.md). Read the user's existing template. Follow the gap analysis framework to present what's covered, what's missing, and any issues. Get approval before modifying.

Get confirmation before proceeding.

---

## Step 3 — Scaffold & Parameterize

Read [references/scaffold.md](references/scaffold.md).

---

## Step 4 — Pre-Deployment Validation

Catch blockers **before** deploying. These checks apply to all paths.

**Sovereign cloud:** Run `az cloud show --query name -o tsv`. If `AzureUSGovernment` or `AzureChinaCloud`, check whether the templates being used (official or user-provided) handle sovereign cloud endpoints. Official templates hardcode `core.windows.net` and Azure Public AAD endpoints.

**RBAC:** Verify deploying identity has Owner, or Contributor + User Access Administrator.

**Policy:** Run `az deployment group what-if`. Fix any violations before deploying.

**Quota:**

```bash
az cognitiveservices account list-skus --location <region> --kind AIServices -o table
```

**Provider Registrations:** `Microsoft.CognitiveServices`, `Microsoft.DocumentDB`, `Microsoft.Search`, `Microsoft.Network`.

**Feature Flags:** For Managed VNet — verify `AI.ManagedVnetPreview` is registered.

> Do NOT deploy until all pre-flight checks pass.

---

## Step 5 — Deploy & Track

**OFFICIAL / ADAPT path:** Read [references/deploy.md](references/deploy.md) for deployment command, monitoring, and error recovery.

**EXTEND path:** Deploy using the user's existing deployment workflow (their CLI commands, pipeline, or CI/CD). The monitoring and error recovery guidance in [references/deploy.md](references/deploy.md) still applies.

---

## Step 6 — Test & Validate

Read [references/post-deployment-validation.md](references/post-deployment-validation.md). These checks apply to all paths — PE verification, RBAC audit, `publicNetworkAccess` audit, and end-to-end agent test work regardless of how the infrastructure was deployed.

If any test fails, run `microsoft_docs_search` for the error before attempting remediation.

---

## Error Handling

> ⚠️ **Critical retry rule:** If a deployment fails after the capability host step starts, the agent subnet gets a `legionservicelink` that cannot be removed. On retry, always use a **new VNet name** — never reuse the same agent subnet. See [references/deploy.md](references/deploy.md).

For all other errors, check `microsoft_docs_search` for current remediation before acting.
