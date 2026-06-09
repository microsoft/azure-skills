# Terraform adapter

Multi-cloud, existing TF state, organization standardized on Terraform.

## Templates

Emit three code files to [`examples/terraform/`](../../examples/terraform/README.md):
- `main.tf` — provider, RG, VNet, subnet, NSG (SSH allow), public IP, NIC, Linux VM
- `variables.tf` — typed input variables with defaults
- `outputs.tf` — `vm_id`, `public_ip`

Always emit `examples/terraform/README.md` (Plan Card, prereqs, quickstart, variables table, outputs, cleanup). When the user requests a PR (Mode C), the same README becomes the PR body.

## Deploy

```bash
terraform init
terraform plan  -var "vm_name={vmName}" -var "admin_public_key=$(cat ~/.ssh/id_rsa.pub)" \
                -var "subscription_id=$AZ_SUB" -var "resource_group_name={resourceGroup}"
terraform apply -var "vm_name={vmName}" -var "admin_public_key=$(cat ~/.ssh/id_rsa.pub)" \
                -var "subscription_id=$AZ_SUB" -var "resource_group_name={resourceGroup}"
```

## VMSS

Replace `azurerm_linux_virtual_machine` with `azurerm_linux_virtual_machine_scale_set` (or Windows variants). Add `instances`, `upgrade_mode = "Manual" | "Automatic" | "Rolling"`. NIC moves inline inside the scale set resource via `network_interface { ip_configuration { ... } }`.

## Notes
- Provider version pinned to `~> 4.0` — bump deliberately, not implicitly.
- `admin_public_key` is `sensitive = true`; don't print it.
- `zone` is `""` by default (regional); to pin, pass `"1"`, `"2"`, or `"3"`.
- Pre-check quota with `compute_vm_check-quota` before `terraform apply`.
