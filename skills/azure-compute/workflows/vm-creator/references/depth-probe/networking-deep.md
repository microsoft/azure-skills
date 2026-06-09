# Networking-deep branch

Ask only what cannot be inferred. Volunteer the advanced switches.

| Topic | Question | Default offered |
|---|---|---|
| VNet | "Existing VNet, or new?" | If existing: ask name + RG; offer to list via `network_vnet_list` MCP or `az network vnet list` |
| Subnet sizing | "Subnet CIDR?" | `/24` if new |
| NSG | "Inbound rules: default (SSH/RDP from your IP) or paste a rule set?" | Restrict source to user's current public IP — fetch via `curl -s ifconfig.me` if not provided |
| Public IP | "Public IP, or private only?" | Public unless user said "private", "internal", "no internet" |
| Accelerated networking | "Enable accelerated networking?" | `true` if size supports it (most D/E/F series ≥ 2 vCPU) |
| Private endpoints | "Any private endpoints to attach?" | Not by default; ask only if user mentioned data / Key Vault / storage targets |
| Outbound | "Outbound: default Azure SNAT, NAT Gateway, or Firewall route?" | Default SNAT if user didn't mention egress; if mentioned, default NAT Gateway |
| DNS | "Custom DNS servers?" | Azure-provided |
| IP version | "IPv4 only or dual-stack?" | IPv4 |
| Service endpoints | "Service endpoints on subnet?" | None unless user mentioned a target |

## Notes

- Don't auto-create a NAT Gateway just because the user said "secure" — confirm intent first; NAT Gateway is ~$30/mo before traffic.
- If the user wants "private only", offer Azure Bastion as the management path; don't silently leave them with no way in.
- `accelerated networking` defaults to **on** for supporting SKUs because the cost is zero and the throughput gain is large.
