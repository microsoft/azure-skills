# Apply via Azure MCP

User is in an MCP-connected host (Claude Code, VS Code Copilot, Cursor) with the Azure MCP server enabled and says "just do it" / "create it now" / "deploy".

## Prerequisite
Azure MCP server installed, and the user is signed in to Azure (e.g. `az login`). The exact auth mechanism is an implementation detail of the MCP server and may vary.

## Pre-flight checks (read-only)

```
compute_vm_check-quota(subscription, location, family={derived from vmSize})
compute_vm_list-skus(subscription, location, familyPrefix={derived from vmSize})
```

Confirm:
- Quota has headroom for the requested vCPU count
- The chosen SKU is available in that region (and zone, if specified)

## Apply — VM

Call `compute_vm_create` with the Plan Card values:

| MCP parameter | Plan Card field |
|---|---|
| `subscription` | subscription |
| `resource-group` | resourceGroup |
| `vm-name` | name |
| `location` | location |
| `image` | image |
| `vm-size` | size |
| `admin-username` | adminUsername |
| `ssh-public-key` (Linux) / `admin-password` (Windows) | sshKey / adminPassword |
| `virtual-network` | vnetName (omit to auto-create) |
| `subnet` | subnetName (omit to auto-create) |
| `network-security-group` | nsgName (omit to auto-create) |
| `public-ip-address` | publicIpName |
| `no-public-ip` | true if Plan Card says private only |
| `source-address-prefix` | restrict NSG inbound source (e.g., user's IP) |
| `zone` | zone |
| `os-disk-size-gb` | osDiskSizeGb |
| `os-disk-type` | osDiskType |
| `os-type` | linux / windows (usually auto-detected from image) |

## Apply — VMSS

Call `compute_vmss_create` with the same fields, plus:

| MCP parameter | Plan Card field |
|---|---|
| `vmss-name` | name |
| `instance-count` | instanceCount |
| `upgrade-policy` | upgradePolicy (Manual / Automatic / Rolling) |

## After apply
- Tool returns `VmCreateResult` / `VmssCreateResult` with `Id`, `Name`, `Location`, `VmSize`, `ProvisioningState`, `PublicIpAddress`, `PrivateIpAddress`, `Zones`, `Tags`.
- Echo back to user: hostname / IP / SSH command (`ssh {adminUsername}@{publicIp}`) or RDP command (`mstsc /v:{publicIp}`).
- Offer next steps: list/inspect (`compute_vm_get`), update (`compute_vm_update`), delete (`compute_vm_delete`).

## Failure handling

| Error | Action |
|---|---|
| `Quota exceeded` | re-run `compute_vm_check-quota`; suggest smaller SKU or different family |
| `A VM with the specified name already exists` | ask for a new name |
| `Resource not found` on RG | create the RG first (`group_create` MCP or `az group create`) |
| `Authorization failed` | user needs Contributor or VM Contributor on the RG |
