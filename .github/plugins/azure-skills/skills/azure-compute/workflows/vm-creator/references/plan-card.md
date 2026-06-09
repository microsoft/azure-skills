# Plan Card

The Plan Card is the single source of truth for the create-flow. It renders **every decision** — explicit user answers and silent defaults — as a markdown table the user can read top-to-bottom and either approve or edit.

## Rendering rules

1. **Cost + quota on the top half.** The user must see both without scrolling.
2. **Source column is mandatory.** Each row says where the value came from: `user`, `default`, `inferred`, or the MCP tool that produced it.
3. **Flag risky defaults with ⚠.** Open NSG to `*`, public IP exposed, no managed identity, password auth on Windows — all get a marker so the user can edit.
4. **No invisible state.** If you defaulted it, it goes in the card.
5. **Re-emit on every change.** When the user edits a row, render the full card again — diffs in chat are easy to miss.

## Schema

| Column | Required? | Notes |
|---|---|---|
| Setting | yes | Human-readable label (`Region`, `Size`, `OS disk`) |
| Value | yes | The concrete value, in backticks if it's a literal |
| Source | yes | `user` / `default` / `inferred` / `<tool name>` |

## Example — Linux dev VM in eastus

```markdown
| Setting | Value | Source |
|---|---|---|
| Hosting model | Single VM | user |
| Name | `dev-vm-01` | default (`<purpose>-vm-<nn>`) |
| Region | `eastus` | user |
| Resource group | `dev-vm-01-rg` (new) | default |
| Image | `Ubuntu2404` | user |
| Size | `Standard_D2s_v5` (2 vCPU / 8 GB) | default |
| Auth | SSH key from `~/.ssh/id_rsa.pub` | inferred |
| VNet | new `dev-vm-01-vnet` (`10.0.0.0/16`) | default |
| Subnet | `default` (`10.0.0.0/24`) | default |
| NSG | SSH 22 from your public IP (`203.0.113.42`) | default — ⚠ change to `*` only if needed |
| Public IP | Standard, dynamic | default |
| OS disk | 30 GB Premium SSD | default |
| Boot diagnostics | Managed | default |
| Estimated cost | ~$0.096/hr (~$70/mo) | from `compute_vm_list-skus` |
| Quota | ✅ 4/100 vCPUs used in `standardDSv5Family` | from `compute_vm_check-quota` |
```

## After rendering — single batched action picker

Render the Plan Card markdown **inline in the chat first** (so the user can read it), then ask **one** AskUserQuestion that combines approval + output format + delivery:

> *"Looks good? Pick how you want it delivered:"*
>
> 1. **Save Bicep to `./infra/{vm-name}/`** *(Recommended for repos)*
> 2. **Print az CLI in chat** *(Quick copy-paste)*
> 3. **Save Terraform to `./infra/{vm-name}/`**
> 4. **Open GitHub PR with Bicep**
> 5. **Apply live via Azure MCP** *(actually creates resources)*
> 6. **Edit a row first** *(then re-render and re-ask)*

This collapses what used to be 3 sequential popups (approve → output format → delivery) into **1**.

Implementation: a single `AskUserQuestion` tool call with `header: "Deliver"`, `multiSelect: false`, and 6 options (the most likely combinations above) — the user can also pick "Other" to type a custom answer like "give me both bicep and terraform".

**If the user picks "Edit a row first":** then ask which row, update, re-render the full Plan Card, and re-ask the same batched action picker. Do not splinter into multiple popups.

**If the user already implied the answer in their original prompt** ("save bicep to ./infra" / "open a PR" / "just print az CLI" / "apply it"): **skip this prompt entirely** and proceed straight to delivery.

**Explicit-override fast path — skip the Plan Card table too.** If the user combines an explicit deliverable ("give me the Bicep", "just print az CLI") with an explicit refusal of dialog ("no questions", "skip planning", "no plan", "just do it"): **do not render the Plan Card markdown table.** Instead emit a single-line preview of the high-signal decisions — e.g. *"→ Deploying `Standard_D2s_v5` in `eastus`, NSG = your public IP only on 22, est. ~$70/mo"* — and follow it immediately with the requested artifact. End with a one-liner noting the full Plan Card is available on request if they want to edit rows. Step 4 validation gates still run.
