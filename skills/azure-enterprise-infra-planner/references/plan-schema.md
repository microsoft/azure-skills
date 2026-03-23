# Infrastructure Plan JSON Schema

The infrastructure plan is written to `<project-root>/.azure/infrastructure-plan.json`. This document describes the schema.

## Top-Level Structure

```json
{
  "meta": { ... },
  "inputs": { ... },
  "plan": { ... }
}
```

## `meta` (required)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `planId` | string | Yes | Unique identifier (e.g., `plan-1`) |
| `generatedAt` | string | Yes | ISO 8601 timestamp |
| `version` | string | Yes | Schema version (e.g., `0.1-draft`) |
| `status` | string | Yes | Lifecycle state: `draft`, `approved`, `deployed` |

## `inputs` (required)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `userGoal` | string | Yes | User's stated objective or workload description, matches user query exactly |
| `subGoals` | string[] | No | Inferred architectural constraints and priorities derived from the user's request and research phase. Examples: `"Cost-optimized: user chose defaults, avoid premium networking"`, `"Security-first: encrypt all data, use managed identity"`, `"Minimal complexity: single region, no VNet"`. These help evaluators understand intentional tradeoffs. Should be short list of 0-3 points. |

## `plan` (required)

### `plan.resources[]` (required)

Each element represents one Azure resource, include resource groups:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Logical resource name (CAF-compliant) |
| `type` | string | Yes | ARM resource type (e.g., `Microsoft.Storage/storageAccounts`) |
| `subtype` | string | No | Exact subtype (e.g., `Blob Storage`, `Azure Function`) |
| `location` | string | Yes | Azure region (e.g., `eastus`) |
| `sku` | string | Yes | SKU tier (e.g., `Standard_LRS`, `Consumption`) |
| `properties` | object | No | Resource-specific properties |
| `reasoning` | object | Yes | See Reasoning below |
| `dependencies` | string[] | Yes | Names of resources this depends on (empty if none) |
| `dependencyReasoning` | string | No | Why these dependencies exist |
| `references` | array | Yes | `[{ "title": "...", "url": "..." }]` links to Azure docs |

### `plan.resources[].reasoning` (required)

| Field | Type | Description |
|-------|------|-------------|
| `whyChosen` | string | Justification referencing WAF pillars (see [research.md](research.md)) or requirements |
| `alternativesConsidered` | string[] | Other options evaluated |
| `tradeoffs` | string | Key tradeoffs in this choice |

### `plan.overallReasoning` (required)

| Field | Type | Description |
|-------|------|-------------|
| `summary` | string | Overall architecture rationale |
| `tradeoffs` | string | Top-level tradeoffs and gaps |

### Other `plan` fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `validation` | string | Yes | Deployment coherence statement |
| `architecturePrinciples` | string[] | Yes | Guiding principles (e.g., `Highly available`, `Secure`) |
| `references` | array | Yes | Architecture-level doc links |

## Example

See [sample_infrastructure_plan.json](./sample_infrastructure_plan.json) for a complete example.
