# Referenced-Workload Handling (on-demand)

> Read this when the user provides something that already EXISTS — a live Azure resource / resource
> group / subscription, IaC (Bicep/Terraform/ARM) or an infra plan, or a general doc describing current
> infrastructure/requirements. If the input is purely NEW requirements with nothing existing, it's
> greenfield — ignore this file and run the normal phases.

## The switched-up flow (referenced mode)
1. **Confirm it's referenced.** Does anything already exist (a resource group/subscription, IaC/plan, or
   a doc describing current resources)? If yes, use this flow.
2. **Inventory the existing resources** from whatever was provided. Capture a COMPLETE inventory — every
   resource type, plus topology/relationships (VNet/subnet, private endpoints, identity bindings) and key
   configurations (SKU/tier, TLS version, public-access setting, region). Do not omit resources or invent
   ones that are not present:
   - **Resource group / subscription** → introspect (`az resource list` / `az graph query`) → real
     resources **with resource IDs**.
   - **IaC / infra plan** (Bicep/Terraform/ARM, `infrastructure-plan.json`, `terraform show -json`) →
     parse `resource` / `existing` / `data` blocks → logical resources.
   - **General doc** → extract any existing resources it mentions.
3. **Gather insights from ALL provided context.** Mine every input the user gave — docs, IaC comments,
   resource tags, requirements, naming conventions, region, resiliency tier, PADU/preferences, cost and
   compliance constraints — and record them as insights (the same channel Phase 3 already applies).
   These shape the new workload just like tenant insights do.
4. **Surface them and ask which to incorporate.** Present the existing resources you found and ask which
   ones to **incorporate** (reference + wire) into the new workload. Recommend a sensible default —
   incorporate the ones the new workload clearly depends on; never recreate them.
5. **Generate the complete IaC** incorporating the chosen (or recommended-default) existing resources:
   reference them (`existing` / `data`, real ID for live, a `param` otherwise) and **wire** the new
   resources to them, honoring the gathered insights. Never emit a new `resource` for something that
   already exists.

## Answer-first (ask AND generate — never stall)
Open with a **plain-language summary of the existing infrastructure** you inventoried and the additive
change you understood, then an **explicit confirmation checkpoint** ("Confirm this understanding before I
proceed to deploy"), and **then** generate the complete, deployable IaC in the SAME response using the
recommended default. Order within the turn: (1) summary of what exists + what you'll add, (2) explicit
"confirm before I proceed" gate, (3) the generated IaC, (4) the "which to incorporate?" choice and any
assumptions. Never end a turn with only a summary or a question, and never deploy before the user
confirms. If you lack a value (region, an existing resource's ID/name), **declare a parameter and
proceed.** The confirmation gate governs deployment (Phase 7), not whether you generate the plan/IaC —
you always generate; you never deploy without an explicit, risk-acknowledged go-ahead.

## Inputs (three shapes → one normalized inventory)
| Shape | Inputs | Referencing precision |
|---|---|---|
| **Actual state** | a live Azure resource, resource group, or subscription | real resource **IDs** → reference exactly (`existing`/`data`) |
| **Declared state** | Bicep / Terraform / ARM, or an infra plan (`infrastructure-plan.json`, `terraform show -json`) | logical → reference by **parameter** (or build, if it's a spec) |
| **Requirements/context** | any general doc with info/requirements the user wants | mine for requirements + any existing-resource mentions |

Inputs can combine (e.g. a resource group + a requirements doc). If a declared file is ambiguous
("reference existing vs. build new?"), make the most likely assumption, state it, and generate — ask at
most one question, after the code.

## For each existing resource, assign a ROLE (the "if needed" filter)
- **Reference + integrate** — the new workload depends on it → reference it AND **wire it in**:
  RBAC role assignment, diagnostics → existing Log Analytics, private endpoints into the existing
  VNet/subnet, secrets from the existing Key Vault, connection to the existing Event Hubs, use the
  existing managed identity, etc.
- **Retain** — keep, must not recreate, nothing new connects → leave it; note "retained, out of scope".
- **Ignore** — irrelevant → omit.

**Never emit a new `resource` for a resource that already exists.** Reference it.

## Deploy (referenced mode)
Referenced mode **does not skip Phase 7** — the deliverable is deployed new infrastructure that
integrates with what already exists. Run [phases/7-deploy.md](phases/7-deploy.md) with these guardrails:

- **Same destructive-action gate.** Present the risks and require an explicit, risk-acknowledged
  "deploy" reply sent *after* the risks are shown. The original prompt never satisfies the gate.
- **Additive only.** The deployment must *add* the new resources and their wiring. The referenced
  resources are declared as `existing`/`data` (not `resource`), so a normal deploy never touches them.
- **Incremental mode, never Complete.** For Bicep use the default **incremental** mode — never
  `--mode Complete` (it would delete resources absent from the template, including the referenced ones).
  For Terraform, the referenced resources are `data` sources / `import`ed, so `apply` must show **no
  destroy** against them — abort if the plan proposes destroying or replacing a referenced resource.
- **Preview first.** Always run `az deployment ... --what-if` (Bicep) or `terraform plan` (Terraform)
  and confirm the diff only *creates* new resources and *modifies nothing* on the referenced ones before
  applying.
- **Deploy into the existing scope when integrating.** Target the referenced resource group/subscription
  so RBAC, private endpoints, and diagnostics wire into the existing resources.


## How this rides the existing phases
- **Phase 1:** normalize the reference into `insights.json` — existing resources (real ID or param),
  `must_not_recreate`, integration points, requirements, tier.
- **Phase 3:** existing "apply insights" logic assigns roles and picks references over new resources.
- **Phase 5:** verify — (a) no duplicate of an existing resource; (b) **every declared dependency on an
  existing resource is actually wired**; (c) cross-module `outputs.X` you consume is declared by that
  module (prevents `BCP053`); (d) source unmodified.
- **Phase 6:** emit new resources (secure-by-default) + `existing`/`data` references + the wiring.
  Real ID inline for actual-state; a `param` for declared/doc inputs.
- **Phase 7:** DO NOT skip deploy — run Phase 7 like greenfield, honoring the destructive-action gate.
  The difference is scope: deploy **only the new resources and their wiring**; never modify, recreate,
  or destroy the referenced/existing resources. See "Deploy (referenced mode)" below.

## Secure-by-default (Phase 6)
Private endpoints + `publicNetworkAccess: Disabled` on data services; managed identity over keys;
storage `allowSharedKeyAccess: false`; Key Vault soft-delete + purge protection; AKS managed identity +
disable local accounts; minimum TLS 1.2.
