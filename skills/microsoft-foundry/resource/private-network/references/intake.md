# Intake

Collect all inputs in one pass, tiered by priority. Extract implicit answers from the user’s message before asking. Use `AskUserQuestion` for unanswered items — batch related questions.

---

## Tier 1 — Core

### 1.0 Verify Subscription

Run:

```bash
az account show --query "{Name:name, Id:id, State:state}" -o table
```

Confirm with user. Switch if needed:

```bash
az account set --subscription "<name-or-id>"
```

### 1.1 Extract Known Answers

Scan the user's message before asking:

| User Says | Inferred |
|-----------|----------|
| "my existing VNet" / "my VNet" | BYO VNet |
| "managed virtual network" | Managed VNet |
| "user-assigned identity" / "UAI" | User-assigned identity |
| "APIM" / "API Management" | Needs APIM |
| "MCP servers on the VNet" | Needs MCP subnet |
| "I have a Bicep/Terraform template" | Extend existing IaC |
| "add Foundry to my existing infra" | Extend existing IaC |

### 1.2 Architecture Questions

For unanswered items, use `AskUserQuestion`:

**VNet model:** BYO VNet or Managed VNet (preview)?

**Agents:** Agent workloads, or just models/projects?

**Region:** Which Azure region? After answer, verify capacity:

```bash
az cognitiveservices account list-skus --location <region> --kind AIServices -o table
```

If empty, warn the user and suggest alternatives.

**Resource Group:** New or existing?

**VNet:** New or existing? If new: address space (default `192.168.0.0/16`), subnet CIDRs (agent `/24`, PE `/24`).

### 1.3 Determine Approach

Based on the answers collected, select one of three paths:

```
User has existing IaC they want to extend?
├── Yes → EXTEND
│
└── No → check template-index.md
    ├── Template fits as-is → OFFICIAL
    └── Partial or no fit → ADAPT (start from closest template)
```

**OFFICIAL:** Load [template-index.md](template-index.md), fetch the best-fit README from GitHub. Present the match using the template's descriptive name.

**ADAPT:** Fetch the closest template's README. Explain what doesn't fit, present the delta, offer to adapt.

**EXTEND:** The user has existing Bicep/Terraform — no template selection needed yet. Continue to Tier 2.

Confirm the approach with the user before continuing to Tier 2.

---

## Tier 2 — Architecture

*Skip questions already answered or not applicable.*

### BYO VNet only

**Topology:** Standalone, hub-spoke, or Azure vWAN?

**On-prem connectivity:** VPN Gateway, ExpressRoute, or none?

**DNS:** Azure-provided, custom DNS resolver, or on-prem DNS forwarding?

**Address space:** Is `192.168.0.0/16` available, or use a specific range?

**NSG / Firewall:** Existing rules on the subnets?

**Deployment executor:** Where will post-deployment commands run? (VM, Bastion, VPN, Cloud Shell)

**Subscription scope:** Same subscription/tenant, cross-subscription, or cross-tenant?

**Team ownership:** Same team controls VNet, DNS, NSG, and policy? If different team, block and get pre-approval before deploying.

### Managed VNet only

**Feature flag:** Run `az feature show` to verify `AI.ManagedVnetPreview` is registered. If not, register and wait 15–30 min.

**Outbound mode:** Internet outbound (default) or approved outbound only?

**MCP:** Public MCP endpoints or private MCP on VNet?

**Client access:** Where will clients connect from? (Same VNet, peered VNet, on-prem via VPN/ER, Azure-hosted service)

### Both paths

**MCP servers:** Needed on VNet?

**APIM:** Needed?

**Identity:** System-assigned (default) or user-assigned?

**BYO resources:** Reuse existing Cosmos DB / Storage / AI Search, or create new?

> If reusing, confirm all in same region as VNet.

**Key Vault / App Insights:** If user mentions existing ones, collect resource IDs. Optional.

---

## Tier 3 — Enterprise

**Agent tools:** Which tools? (AI Search, Cosmos DB, Storage, MCP, external APIs, Bing grounding, Code Interpreter)

**Model:** Name, vendor, version. Verify version format:

| Vendor | Format | Example |
|--------|--------|---------|
| OpenAI | Date | `2025-04-14` |
| Mistral AI | Integer | `1` |
| Meta | Integer | `9` |

**Client type:** SDK, web app, Teams bot, other service?

**Client network path:** Inside VNet, peered VNet, VPN/ExpressRoute?

**Authentication:** Entra ID (recommended) or API key?

> Entra ID token audience for Foundry Agents API: `https://ai.azure.com`

**GitHub access:** Can deployment environment reach `github.com`? If not, pre-stage template.

**Azure Policy:** Known policies (e.g., `disableLocalAuth`, `defaultOutboundAccess`)? If unknown, `what-if` catches them in Step 4.

**Monitoring:** Existing Log Analytics workspace, create new, or not needed?

---

## Validate Against Learn

After collecting all requirements, validate the user's configuration against current documentation. Use `microsoft_docs_fetch` on the relevant pages below, then `microsoft_docs_search` for any requirement-specific concerns not covered.

### Reference Pages

| Topic | URL |
|-------|-----|
| Network isolation overview | https://learn.microsoft.com/azure/ai-foundry/how-to/configure-private-link |
| Agent Service private networking | https://learn.microsoft.com/azure/ai-services/agents/how-to/virtual-networks |
| Managed VNet configuration | https://learn.microsoft.com/azure/ai-foundry/how-to/configure-managed-network |
| Agent Service FAQ — VNet | https://learn.microsoft.com/azure/foundry/agents/faq#virtual-networking |
| Supported regions & availability | https://learn.microsoft.com/azure/ai-foundry/reference/region-support |
| NSP | https://learn.microsoft.com/en-us/azure/networking/network-security-perimeter |
| Feature Limitations | https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-private-link#foundry-feature-limitations |

> These URLs may change. If a fetch returns 404, use `microsoft_docs_search` to find the current page.

If a conflict is found, present:
1. The constraint and its source URL
2. Which requirement it affects
3. Options to resolve

Do NOT proceed until all conflicts are resolved or accepted.

---

## Confirmation

Present a summary of all gathered requirements. Ask: **"Confirm this is accurate before I generate a deployment plan."**

> Do NOT proceed to Plan Generation until you validated requirements against documents and the user confirms.
