# Cannot Connect to VM

Index of VM connectivity troubleshooting references. Route to the appropriate file based on the user's symptom category.

> ⚠️ **Determine OS first.** If the user hasn't stated their OS, check via CLI (`az vm get-instance-view`) or ask. OS matters because:
> - **Windows** → RDP (port 3389), Windows Firewall, TermService, PowerShell Run Commands
> - **Linux** → SSH (port 22), iptables/firewalld/UFW, sshd, Shell Run Commands
> - **Other images** (FreeBSD, Flatcar, etc.) → SSH; firewall and init systems vary — fetch the latest docs

## Routing

| Signal in User Message                                                         | Category                  | Reference                                                  |
| ------------------------------------------------------------------------------ | ------------------------- | ---------------------------------------------------------- |
| "can't RDP", timeout, black screen, RDP error, internal error                  | Unable to RDP             | [rdp-connectivity.md](rdp-connectivity.md)                 |
| "can't SSH", refused, permission denied, publickey                             | Unable to SSH             | [ssh-connectivity.md](ssh-connectivity.md)                 |
| NSG, no public IP, NIC disabled, routing, effective rules                      | Network Issues            | [network-connectivity.md](network-connectivity.md)         |
| Guest firewall, Windows Firewall, iptables, firewalld, BlockInboundAlways      | Firewall Blocking         | [firewall-blocking.md](firewall-blocking.md)               |
| VM agent down, Run Command timeout, Serial Console, boot diagnostics, BSOD     | VM Agent Not Responding   | [vm-agent-not-responding.md](vm-agent-not-responding.md)   |
| Wrong password, credentials, access denied, CredSSP, account expired           | Credential / Auth Errors  | [credential-auth-errors.md](credential-auth-errors.md)     |
| TermService stopped, RDP disabled, port changed, TLS cert, NLA, GPO, licensing | RDP Service / Config      | [rdp-service-config.md](rdp-service-config.md)             |

## Workflow

1. Identify the symptom category from the routing table above
2. Open the matching reference file for the Symptoms → Solutions table and Quick Commands
3. Narrow to the specific solution row matching the user's symptom
4. Fetch the linked documentation URL for the latest guidance
5. Summarize diagnostic steps and resolution, referencing the official docs

---

## Escalation

If the issue doesn't match any symptom above, or if the documented solutions don't resolve it:

1. **Check Azure Resource Health** — Portal > VM > Resource health (checks for platform-level issues)
2. **Restart the VM** — `az vm restart --name <vm-name> -g <resource-group>`
3. **Redeploy the VM** — `az vm redeploy --name <vm-name> -g <resource-group>` (moves to new host)
4. **Comprehensive troubleshooting:**
   - Windows: [Troubleshoot RDP connections](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-connection)
   - Linux: [Troubleshoot SSH connections](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)
   - Windows hub: [All Windows VM troubleshooting docs](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/welcome-virtual-machines-windows)
   - Linux hub: [All Linux VM troubleshooting docs](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/welcome-virtual-machines-linux)