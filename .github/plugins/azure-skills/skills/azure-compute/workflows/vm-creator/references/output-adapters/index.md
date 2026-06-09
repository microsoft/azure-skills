# Output Adapters

The VM Creator's final step emits the user's choice of one (or more) output formats from the same approved Plan Card. The user can re-emit a different format at any time without restarting the conversation.

## Choosing the format

| Format | When to offer | File |
|---|---|---|
| **az CLI bash** | Quick one-off, learning, ad-hoc creation, CI scripts | [az-cli.md](az-cli.md) |
| **Bicep** | Production IaC, repeatable, what-if preview, org standardized on Bicep | [bicep.md](bicep.md) |
| **Terraform** | Multi-cloud, existing TF state, org standardized on Terraform | [terraform.md](terraform.md) |
| **Apply via Azure MCP** | "Just do it" — user is in an MCP-connected host and trusts the Plan Card | [mcp-apply.md](mcp-apply.md) |

Always show the user all four as a numbered choice at Step 6. Default-suggest based on signals:
- "I want a script" → az CLI
- "I want infra-as-code" → Bicep (default) / Terraform (if user mentioned TF)
- "Just create it" / "deploy it now" → Apply via Azure MCP

## Plan Card → parameter mapping

Every adapter draws from these Plan Card fields. Capture them once; transform on emit.

| Plan Card field | az CLI | Bicep | Terraform | MCP parameter |
|---|---|---|---|---|
| name | `--name` | `vmName` | `vm_name` | `vm-name` |
| resourceGroup | `--resource-group` | (scope) | `resource_group_name` | `resource-group` |
| subscription | `--subscription` | (scope) | `subscription_id` | `subscription` |
| location | `--location` | `location` | `location` | `location` |
| size | `--size` | `vmSize` | `size` | `vm-size` |
| image | `--image` | `imageReference` | `source_image_reference` | `image` |
| adminUsername | `--admin-username` | `adminUsername` | `admin_username` | `admin-username` |
| sshKey | `--ssh-key-values` | `adminPublicKey` | `admin_ssh_key.public_key` | `ssh-public-key` |
| adminPassword | `--admin-password` | `adminPassword` (secure) | `admin_password` (sensitive) | `admin-password` |
| vnetName | `--vnet-name` | `vnetName` | `azurerm_virtual_network.name` | `virtual-network` |
| subnetName | `--subnet` | `subnetName` | `azurerm_subnet.name` | `subnet` |
| publicIp | `--public-ip-address` | `publicIpName` | `azurerm_public_ip` | `public-ip-address` |
| nsgName | `--nsg` | `nsgName` | `azurerm_network_security_group.name` | `network-security-group` |
| zone | `--zone` | `zones: [N]` | `zone` | `zone` |
| osDiskType | `--storage-sku` | `osDisk.managedDisk.storageAccountType` | `os_disk.storage_account_type` | `os-disk-type` |
| osDiskSizeGb | `--os-disk-size-gb` | `osDisk.diskSizeGB` | `os_disk.disk_size_gb` | `os-disk-size-gb` |
| tags | `--tags` | `tags` | `tags` | (none — emit separately) |

For VMSS, also map `instanceCount` and `upgradePolicy` (see each adapter file).

## Re-emitting after a format switch

After the user picks one format, save the Plan Card. If they later say "actually give me the bicep too" or "show me terraform", regenerate from the same Plan Card — do not re-ask any questions. The Plan Card is the canonical state.
