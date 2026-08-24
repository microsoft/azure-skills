# Infrastructure Plan Schema

```ts
{
  meta: {
    planId: string // Unique identifier (e.g., "plan-1")
    generatedAt: string // ISO 8601 timestamp
    version: string // Schema version (e.g., "0.1-draft")
    status: "draft" | "approved" | "deployed" // Lifecycle state
  }
  inputs: {
    userGoal: string // User's stated objective or workload description, matches user query exactly
    subGoals?: string[] // Inferred architectural constraints and priorities derived from the user's request and research phase. Examples: "Cost-optimized: user chose defaults, avoid premium networking", "Security-first: encrypt all data, use managed identity", "Minimal complexity: single region, no VNet". These help evaluators understand intentional tradeoffs. Should be short list of 0-3 points.
    insightsApplied: string[] // For each insight that influenced this plan, cite the insight ID and explain how and why it was applied. Set to an empty array if no insights were applied. Document any unapplied insights in plan.overallReasoning.tradeoffs.
  }
  plan: {
    resources: {
      name: string // Logical resource name (CAF-compliant)
      type: string // ARM resource type (e.g., "Microsoft.Storage/storageAccounts")
      subtype?: string // Exact subtype (e.g., "Blob Storage", "Azure Function")
      location: string // Azure region (e.g., "eastus")
      sku: string // SKU tier (e.g., "Standard_LRS", "Consumption")
      properties?: Record<string, unknown> // Resource-specific properties
      reasoning: {
        whyChosen: string // Justification referencing WAF pillars (see phases/2-research-best-practices.md and phases/3-research-resources.md) or requirements
        alternativesConsidered: string[] // Other options evaluated
        tradeoffs: string // Key tradeoffs in this choice
      }
      dependencies: string[] // Names of resources this depends on (empty if none)
      dependencyReasoning?: string // Why these dependencies exist
      references: { title: string, url: string }[] // Links to Azure docs
    }[]
    overallReasoning: {
      summary: string // Overall architecture rationale
      tradeoffs: string // Top-level tradeoffs and gaps
    }
    validation: string // Deployment coherence statement
    architecturePrinciples: string[] // Guiding principles (e.g., "Highly available", "Secure")
    references: { title: string, url: string }[] // Architecture-level doc links
  }
}
```

## Insights Schema

```ts
type ExistingResource = {
  id: string // Full ARM ID for actual state; logical or parameter reference otherwise
  type: string // ARM resource type (e.g., "Microsoft.Network/virtualNetworks")
  name: string
  role: "reference-and-integrate" | "retain" | "ignore"
  must_not_recreate: true
  integrationPoints: string[] // Connections or dependencies involving the new workload
}

type Insight =
  | {
      id: string // Stable identifier (e.g., "insight-001"); cited from inputs.insightsApplied
      pattern: string // Observed fact from the tenant scan or referenced workload
      implication: string // Recommended planning action derived from the pattern
      existingResource?: ExistingResource
    }
  | {
      id: string // Stable identifier for a resource-only entry
      existingResource: ExistingResource
      pattern?: string // Include with implication when the resource produces a broader insight
      implication?: string
    }

type Insights = Insight[]
```

In referenced mode:

- Include exactly one entry for every inventoried existing resource, uniquely identified by `existingResource.id`.
- Preserve the full ARM ID in `existingResource.id` for actual-state resources.
- Use an empty `integrationPoints` array when the resource has no integration points.
- A resource-only entry may omit `pattern` and `implication`; when recording a broader insight, include both.
