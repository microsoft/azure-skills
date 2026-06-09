# MCP tools used by vm-creator

The Azure MCP server exposes the `compute` area as a single namespace proxy: `mcp__azure__compute({intent, command, parameters})`. The commands below are what the workflow dispatches against it.

## Read-only validation (Step 4)

| Command | Purpose | Key parameters |
|---|---|---|
| `compute_vm_list-skus` | Confirm SKU availability + filter by vCPU/memory/family | `subscription`, `location`, `minVCpus`, `minMemoryGb`, `familyPrefix`, `top` |
| `compute_vm_list-images` | Resolve image alias / URN | `subscription`, `location`, `publisher`, `offer`, `sku` |
| `compute_vm_check-quota` | Verify vCPU headroom for the family | `subscription`, `location`, `family` |
| `compute_vm_recommend-region` | Find regions where the workload fits | workload hints; returns ranked regions |

## Apply (Step 6, Adapter 4)

| Command | Purpose |
|---|---|
| `compute_vm_create` | Create a single VM from Plan Card fields |
| `compute_vmss_create` | Create a VMSS (adds `instance-count`, `upgrade-policy`) |
| `compute_vm_get` | Inspect after create |
| `compute_vm_update` | Tag changes, size resize, identity attach |
| `compute_vm_delete` | Cleanup |

See [output-adapters/mcp-apply.md](output-adapters/mcp-apply.md) for the full parameter mapping and failure-handling table.

## CLI fallbacks (when Azure MCP is not connected)

| MCP command | CLI equivalent |
|---|---|
| `compute_vm_list-skus` | `az vm list-skus --location <region> --output table` |
| `compute_vm_list-images` | `az vm image list --location <region> --offer <offer> --all` |
| `compute_vm_check-quota` | `az vm list-usage --location <region> --output table` |
| `compute_vm_recommend-region` | (no CLI equivalent — fall back to docs) |
| `compute_vm_create` | `az vm create ...` (see [az-cli.md](output-adapters/az-cli.md)) |

## Why the proxy form matters

The CLI / tool host shows `mcp__azure__compute` as a single tool. Sub-operations like `vm check-quota`, `vm list-skus`, etc. are not separate tools — they are passed through the `command` parameter. Every command is invoked as:

```
mcp__azure__compute({
  command: "vm check-quota",
  parameters: { location: "eastus", family: "standardDSv5Family" }
})
```

When tracing tool calls or writing must-call rubrics, look for the `command=` argument, not a distinct tool name.
