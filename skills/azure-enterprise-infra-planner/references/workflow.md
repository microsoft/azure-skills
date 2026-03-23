# Workflow — Azure Enterprise Infra Planner

## Rules

1. **Research before planning** — You **MUST** call `mcp_azure_mcp_get_azure_bestpractices` and `mcp_azure_mcp_wellarchitectedframework` MCP tools BEFORE reading local resource files or generating a plan. See [research.md](research.md) Step 2.
2. **Plan before IaC** — Generate `<project-root>/.azure/infrastructure-plan.json` before any IaC so we can map the plan to generated code and ensure alignment.
3. **Get approval** — Plan status must be `approved` before deployment.
4. **User chooses IaC format** — Bicep or Terraform; ask if not specified.
5. ⚠️ **Destructive actions require explicit confirmation.**

---

> **Complete each phase fully before starting the next. Phases are sequential, not parallel.**

## Phase 1: Research — WAF Tools
Call MCP tools to gather best practices and WAF guidance. See [research.md](research.md) Steps 1-2.
- Call `get_azure_bestpractices` once (direct call — small response)
- Call `wellarchitectedframework_serviceguide_get` for each core service (direct parallel calls — small responses, returns URLs only)
- Use **sub-agents** to fetch and summarize each WAF guide URL (large responses — 20-60KB each)

**Gate**: All WAF tool calls complete and summarized before proceeding.

## Phase 2: Research — Refine & Lookup

> ⚠️ **You MUST look up resources before generating the plan.** The [resources/](resources/README.md) directory contains ARM types, API versions, CAF prefixes, naming rule URLs, and region categories that MCP tools do not provide.

Apply WAF findings, then look up every resource in local reference files. See [research.md](research.md) Steps 3-4.
- Walk through [waf-checklist.md](waf-checklist.md) — add missing resources, document omissions
- Read [resources/README.md](resources/README.md) to identify which category files to load, then read only the relevant category files (e.g., `resources/compute-infra.md` for AKS, `resources/security.md` for Key Vault)
- For each resource: use **sub-agents** to fetch naming rules via `microsoft_docs_fetch` using URLs from the resource category files
- For each resource: read pairing constraints from the matching [constraints/](constraints/README.md) category file (e.g., `constraints/networking-core.md` for VNet)

**Gate**: Every resource has an ARM type, naming rules, and pairing constraints checked. Present the preliminary resource list to the user with brief justifications and **STOP — wait for approval**.

## Phase 3: Plan Generation
Build `<project-root>/.azure/infrastructure-plan.json` using the schema in [plan-schema.md](plan-schema.md). Set `meta.status` to `draft`.

**Gate**: Plan JSON written to disk before proceeding.

## Phase 4: Verification
Run a full verification pass on the generated plan. See [verification.md](verification.md) and [pairing-checks.md](pairing-checks.md).
- Check goal coverage — does every user requirement map to a resource?
- Check dependency completeness — every `dependencies[]` entry resolves
- Check pairing constraints — SKU compatibility, subnet conflicts, storage pairing
- Fix issues in-place in the plan JSON

**Gate**: All verification checks pass. Present plan to user and **STOP — wait for approval**.

## Phase 5: IaC Generation
Generate Bicep or Terraform from the approved plan. You must refer to instructions in [bicep-generation.md](bicep-generation.md) for Bicep or [terraform-generation.md](terraform-generation.md) for Terraform.

**Gate**: `meta.status` must be `approved` before generating any IaC files.

## Phase 6: Deployment
Execute deployment commands. See [deployment.md](deployment.md).
- Confirm subscription and resource group with user
- Select the correct deployment scope based on `targetScope` in `main.bicep` (resource group, subscription, management group, or tenant)
- Run `az bicep build` to validate, then execute the matching scope command (`az deployment group create`, `az deployment sub create`, etc.) or `terraform apply`

**Gate**: `meta.status` must be `approved`. Destructive actions require explicit user confirmation.

## Status Lifecycle

`draft` → `approved` → `deployed`

---

## Outputs

| Artifact | Location |
|----------|----------|
| **Infrastructure Plan** | `<project-root>/.azure/infrastructure-plan.json` |
| Bicep files | `<project-root>/infra/main.bicep`, `<project-root>/infra/modules/*.bicep` |
| Terraform files | `<project-root>/infra/main.tf`, `<project-root>/infra/modules/**/*.tf` |

> ⚠️ **IaC file placement is mandatory.** Before writing any `.bicep` or `.tf` files:
> 1. Create the `infra/` directory at `<project-root>/infra/`
> 2. Create `infra/modules/` for child modules
> 3. Write `main.bicep` (or `main.tf`) inside `infra/`, NOT in the project root or `.azure/`

