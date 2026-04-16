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
4. **Before any extension-backed operation, run [Pre-Flight Safety Checks](#pre-flight-safety-checks)**
5. Fetch the linked documentation URL for the latest guidance
6. Summarize diagnostic steps and resolution, referencing the official docs

---

## Pre-Flight Safety Checks

> ⚠️ **Warning:** Always run these checks before any command that depends on the VM agent or extensions (`az vm user update`, `az vm user reset-ssh`, `az vm user reset-remote-desktop`, `az vm run-command invoke`). Running extension-backed operations on a VM with an unhealthy agent or stuck extensions can **deadlock the VM** and require manual portal recovery.

```bash
# 1. Check VM power state, provisioning state, and agent status
az vm get-instance-view --name <vm-name> -g <resource-group> \
  --query "instanceView.{powerState:[statuses[?starts_with(code,'PowerState/')]][0][0].code, provisioningState:[statuses[?starts_with(code,'ProvisioningState/')]][0][0].code, vmAgentStatus:vmAgent.statuses[0].displayStatus}" -o json

# 2. Check existing extension states
az vm extension list --vm-name <vm-name> -g <resource-group> \
  --query "[].{name:name, provisioningState:provisioningState}" -o table
```

| Check | Safe Value | Unsafe — Do NOT proceed |
| ----- | ---------- | ----------------------- |
| Power state | `PowerState/running` | Any other value, missing, or query error |
| Provisioning state | `ProvisioningState/succeeded` | `Updating`, `Creating`, `Failed`, `Deleting`, missing, or query error |
| VM agent status | `Ready` | `Not Ready`, `null`, missing, or query error |
| Extension states | All `Succeeded` or no extensions | Any extension in `Creating`, `Updating`, `Deleting`, or `Failed` |

> 💡 **Tip:** If a check returns `null`, empty, or the CLI command itself errors, treat the result as **unsafe**.

**If any check is unsafe:**
1. **Stop.** Do NOT run any extension-backed command.
2. Inform the user which check(s) failed and what the current state is.
3. Use non-agent alternatives: **Serial Console**, **offline repair VM**, or **Portal-based actions**.
4. If the state appears transient (e.g., VM just started, provisioning briefly not `succeeded`), wait 30–60 seconds and **re-run the checks only** — do not run the extension command until all checks pass.

---

## Escalation

If the issue doesn't match any symptom above, or if the documented solutions don't resolve it:

1. **Check Azure Resource Health** — Portal > VM > Resource health (checks for platform-level issues)
2. **Offer to restart the VM** (requires user approval) — `az vm restart --name <vm-name> -g <resource-group>`
3. **Offer to redeploy the VM** (requires user approval — moves to new host) — `az vm redeploy --name <vm-name> -g <resource-group>`
4. **Comprehensive troubleshooting:**
   - Windows: [Troubleshoot RDP connections](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-connection)
   - Linux: [Troubleshoot SSH connections](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)
   - Windows hub: [All Windows VM troubleshooting docs](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/welcome-virtual-machines-windows)
   - Linux hub: [All Linux VM troubleshooting docs](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/welcome-virtual-machines-linux)