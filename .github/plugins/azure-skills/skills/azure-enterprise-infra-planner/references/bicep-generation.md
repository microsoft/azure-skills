# Bicep Generation

Generate Bicep IaC files from the approved infrastructure plan.

> ⚠️ **CRITICAL**: All Bicep files MUST be created under `<project-root>/infra/`. Never place `.bicep` files in the project root or in `.azure/`.

## File Structure

Generate files under `<project-root>/infra/`:

```
infra/
├── main.bicep              # Orchestrator — deploys all modules
├── main.bicepparam         # Parameter values
└── modules/
    ├── storage.bicep        # One module per resource or logical group
    ├── compute.bicep
    ├── networking.bicep
    └── monitoring.bicep
```

## Generation Steps

1. **Create `infra/` directory** — Create `<project-root>/infra/` and `<project-root>/infra/modules/` directories. All files in subsequent steps go here.
2. **Read plan** — Load `<project-root>/.azure/infrastructure-plan.json`, verify `meta.status === "approved"`
3. **Fetch Bicep schemas** — For each resource in the plan, use a sub-agent to call `bicepschema_get` with `resource-type` set to the ARM type from the relevant [resources/](resources/README.md) category file (e.g., `Microsoft.ContainerService/managedClusters`). Instruct the sub-agent: "Return the full property structure for {ARM type}: required properties, allowed values, child resources. ≤500 tokens." Use this output — not training data — to generate correct resource definitions.

   > ⚠️ **Sub-resource vs parent schemas**: The schema tool returns only the schema for the exact type requested. Sub-resource types (e.g., `Microsoft.Network/virtualNetworks/subnets`) return a smaller, focused schema but **miss parent-level properties** (e.g., VNet `encryption` lives on the parent, not the subnet sub-resource). Strategy:
   > - **Start with sub-resource types** when validating child resources — smaller responses (~25KB vs ~95KB), easier to summarize
   > - **Fetch the parent type separately** when you need parent-level properties (encryption, tags, SKU) — delegate to a sub-agent with specific property extraction instructions to manage the large response

4. **Generate modules** — Group resources by category; one `.bicep` file per group under `infra/modules/`. Use the schema from step 3 for property names, allowed values, and required fields.
5. **Generate main.bicep** — Write `infra/main.bicep` that imports all modules and passes parameters
6. **Generate parameters** — Create `infra/main.bicepparam` with environment-specific values

## Bicep Conventions

- Use `@description()` decorators on all parameters
- Use `@secure()` for secrets and connection strings
- Choose `targetScope` in `main.bicep` based on the deployment plan:
  - For **single resource group** deployments, set `targetScope = 'resourceGroup'` and deploy with `az deployment group create`.
  - For **subscription-scope** deployments (for example, resources across multiple resource groups or subscription-level resources), set `targetScope = 'subscription'` and deploy with `az deployment sub create`.
- Use `existing` keyword for referencing pre-existing resources
- Output resource IDs and endpoints needed by other resources
- Use `dependsOn` only when implicit dependencies are insufficient

## Parameter File Format

```bicep
using './main.bicep'

param location = 'eastus'
param environmentName = 'prod'
param workloadName = 'datapipeline'
```

## Multi-Environment

For multi-environment plans, generate one parameter file per environment:

```txt
infra/
├── main.bicep
├── main.dev.bicepparam
├── main.staging.bicepparam
└── main.prod.bicepparam
```

## Validation Before Deployment

Run `az bicep build --file infra/main.bicep` to validate syntax before deploying.
