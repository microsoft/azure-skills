# Hand-off to vm-creator

When the user wants to **provision** the recommended option (not just compare), hand off to [vm-creator](../../vm-creator/vm-creator.md). Don't skip directly to an output adapter — the user must see and approve the Plan Card first.

## Required before hand-off

Render the [Plan Card](../../vm-creator/references/plan-card.md) markdown table **in chat** with the chosen SKU, region, instance count, pricing, and quota status pre-filled from the recommender's work. The user is approving the Plan Card, not the artifact.

## Routing signals

| User says | Action |
|---|---|
| "let's create it" / "spin one up" / "deploy this" | Render Plan Card → route to `vm-creator` Step 5 with selected SKU + region pre-filled |
| "give me the az CLI / Bicep / Terraform" | Render Plan Card → route to `vm-creator` Step 6 (Output Choice) |
| "just compare prices" / "I'm still deciding" | Stay in `vm-recommender`; offer to revisit |

## Example hand-off message

> *"Want me to generate the create command? I can output az CLI, Bicep, Terraform, or apply it via Azure MCP — I'll carry over the SKU, region, and pricing we just landed on."*

## What carries over

| Recommender output | Plan Card row |
|---|---|
| Hosting Model (VM vs VMSS) | `Hosting model` |
| VM Size (ARM SKU) | `Size` |
| Region | `Region` |
| Instance Count (or `min–max`) | `Instance count` (VMSS only) |
| Estimated $/hr | `Estimated cost` |
| Quota Status (✅/⚠️/❌) | `Quota` |

`vm-creator` Steps 2–4 (Depth Probe, Adaptive Gather, Validate) still run after hand-off to fill in OS, auth, networking, and tagging — they're additive on top of the recommender's spec choice.
