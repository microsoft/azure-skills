# az CLI adapter

Fast, portable, scriptable. Works anywhere `az` is installed and logged in.

## VM template

```bash
#!/usr/bin/env bash
set -euo pipefail

# {plan-card-summary}

az group create --name "{resourceGroup}" --location "{location}"

az vm create \
  --resource-group "{resourceGroup}" \
  --name "{vmName}" \
  --location "{location}" \
  --image "{image}" \
  --size "{vmSize}" \
  --admin-username "{adminUsername}" \
  --ssh-key-values @{sshKeyPath} \
  --vnet-name "{vnetName}" \
  --subnet "{subnetName}" \
  --nsg "{nsgName}" \
  --public-ip-address "{publicIpName}" \
  --zone {zone} \
  --os-disk-size-gb {osDiskSizeGb} \
  --storage-sku {osDiskType} \
  --tags {tagsKv}
```

## VMSS template

Replace `az vm create` with `az vmss create`, swap `--size` for `--vm-sku`, add `--instance-count {n}`, `--orchestration-mode Flexible`, `--upgrade-policy-mode Manual|Automatic|Rolling`.

## Filled example — dev Linux VM in eastus

```bash
#!/usr/bin/env bash
set -euo pipefail

# dev-vm | eastus | Ubuntu2404 | Standard_D2s_v5 | new VNet | est. $70/mo

az group create --name dev-vm-rg --location eastus

az vm create \
  --resource-group dev-vm-rg \
  --name dev-vm \
  --location eastus \
  --image Ubuntu2404 \
  --size Standard_D2s_v5 \
  --admin-username azureuser \
  --ssh-key-values @~/.ssh/id_rsa.pub \
  --vnet-name dev-vm-vnet \
  --subnet default \
  --nsg dev-vm-nsg \
  --public-ip-address dev-vm-ip \
  --os-disk-size-gb 30 \
  --storage-sku Premium_LRS \
  --tags env=dev owner=team-name
```

## Notes
- Windows VMs: swap `--ssh-key-values @...` for `--admin-password '{password}'`.
- Linux: prefer SSH keys (`~/.ssh/id_rsa.pub` or `~/.ssh/id_ed25519.pub`). Never paste private keys.
- `--zone` is optional; omit the flag entirely (don't pass empty) for regional VMs.
- `--tags` uses space-separated `k=v` pairs.
- Pre-check quota: `compute_vm_check-quota` (or `az vm list-usage --location {location} -o table`).
