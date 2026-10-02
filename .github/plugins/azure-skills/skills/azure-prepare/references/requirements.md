# Requirements Gathering

Collect project requirements through conversation before making architecture decisions.

## Categories

### 1. Classification

| Type | Description | Implications |
|------|-------------|--------------|
| POC | Proof of concept | Minimal infra, cost-optimized |
| Development | Internal tooling | Balanced, team-focused |
| Production | Customer-facing | Full reliability, monitoring |

### 2. Scale

| Scale | Users | Considerations |
|-------|-------|----------------|
| Small | <1K | Single region, basic SKUs |
| Medium | 1K-100K | Auto-scaling, multi-zone |
| Large | 100K+ | Multi-region, premium SKUs |

### 3. Budget

| Profile | Focus |
|---------|-------|
| Cost-Optimized | Minimize spend, lower SKUs |
| Balanced | Value for money, standard SKUs |
| Performance | Maximum capability, premium SKUs |

### 4. Compliance

| Requirement | Impact |
|-------------|--------|
| Data residency | Region constraints |
| Industry regulations | Security controls |
| Internal policies | Approval workflows |

### 5. Subscription Policies

After the user confirms a subscription, query Azure Policy assignments to discover enforcement constraints before making architecture decisions.

```
mcp_azure_mcp_policy(command: "policy_assignment_list", subscription: "<subscriptionId>")
```

| Policy Constraint | Impact |
|-------------------|--------|
| Blocked resource types or SKUs | Exclude from architecture |
| Required tags | Add to all Bicep/Terraform resources |
| Allowed regions | Restrict location choices |
| Network restrictions (e.g., no public endpoints) | Adjust networking and access patterns |
| Storage policies (e.g., deny shared key access) | Use policy-compliant auth |
| Naming conventions | Apply to resource naming |

> ⚠️ **Warning:** Skipping this step can cause deployment failures when Azure Policy denies resource creation. Checking policies here prevents wasted work in architecture and generation phases.

Record discovered policy constraints in `.azure/deployment-plan.md` under a **Policy Constraints** section so they feed into architecture decisions.

## Gather via Conversation

Use `ask_user` tool to confirm each of these with the user:

1. Project classification (POC/Dev/Prod)
2. Expected scale
3. Budget constraints
4. Compliance requirements (including data residency preferences)
5. Subscription and policy constraints (confirm subscription, then check policies automatically)
6. Architecture preferences (if any)

## Document in Plan

Record all requirements in `.azure/deployment-plan.md` immediately after gathering.
