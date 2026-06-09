# {vm-name} — Terraform

Deploys a Linux VM (RG, VNet, subnet, NSG with SSH allow, public IP, NIC).

## Prerequisites
- `terraform >= 1.5`
- `az login`
- Exported `AZ_SUB=<subscription-id>` env var
- SSH public key at `~/.ssh/id_rsa.pub`

## Quickstart

```bash
MY_IP=$(curl -s ifconfig.me)/32   # your current public IP, locked to /32
terraform init
terraform plan  -var "vm_name=dev-vm" -var "admin_public_key=$(cat ~/.ssh/id_rsa.pub)" -var "subscription_id=$AZ_SUB" -var "resource_group_name=dev-vm-rg" -var "ssh_source_address_prefix=$MY_IP"
terraform apply -var "vm_name=dev-vm" -var "admin_public_key=$(cat ~/.ssh/id_rsa.pub)" -var "subscription_id=$AZ_SUB" -var "resource_group_name=dev-vm-rg" -var "ssh_source_address_prefix=$MY_IP"
```

## Variables (see `variables.tf`)

| Variable | Type | Default | Notes |
|---|---|---|---|
| `subscription_id` * | string | — | Azure subscription |
| `resource_group_name` * | string | — | RG will be created |
| `vm_name` * | string | — | VM resource name |
| `admin_public_key` * | string (sensitive) | — | Contents of `id_rsa.pub` |
| `ssh_source_address_prefix` * | string | — | Your public IP as `<ip>/32` or a trusted CIDR. `"*"` opens port 22 to the internet — only pass it if you have accepted that risk. |
| `location` | string | `eastus` | Azure region |
| `size` | string | `Standard_D2s_v5` | Verify with `compute_vm_list-skus` |
| `admin_username` | string | `azureuser` | |
| `zone` | string | `""` | `1`/`2`/`3`, or empty for regional |
| `os_disk_type` | string | `Premium_LRS` | |
| `os_disk_size_gb` | number | `30` | |
| `tags` | map(string) | `{}` | |

`*` = required (no default).

## Outputs (see `outputs.tf`)
- `vm_id` — full ARM resource ID
- `public_ip` — connect with `ssh {admin_username}@{public_ip}`

## VMSS variant
Replace `azurerm_linux_virtual_machine` with `azurerm_linux_virtual_machine_scale_set`; add `instances`, `upgrade_mode = "Manual" | "Automatic" | "Rolling"`. Inline NIC inside the scale set via `network_interface { ip_configuration { ... } }`.

## Notes
`ssh_source_address_prefix` is required because an open SSH port is a credential-stuffing target within minutes of going public. Always pass `<your-ip>/32` (or a trusted CIDR) — even for dev. For production, also add managed identity, diagnostics, and backup.

## Cleanup
```bash
terraform destroy -var "vm_name=dev-vm" -var "admin_public_key=$(cat ~/.ssh/id_rsa.pub)" -var "subscription_id=$AZ_SUB" -var "resource_group_name=dev-vm-rg" -var "ssh_source_address_prefix=$MY_IP" -auto-approve
```
