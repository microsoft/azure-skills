# Cannot Connect to VM

When to use this reference file: when the user is facing connectivity issues with their Azure VM, such as:

- Unable to RDP/SSH into the VM
- Network connectivity problems (NSG rules, firewall, routing)
- VM agent not responding
- Credential or authentication errors
- Black screen or RDP disconnections
- RDP service or configuration issues

## Workflow

1. Identify the specific connectivity issue from the symptom categories below
2. Narrow down to a specific solution item
3. Fetch the relevant troubleshooting URL for the latest guidance
4. Summarize the key steps to diagnose and resolve, referencing the official documentation

---

## Unable to RDP into the VM

User is trying to RDP into a Windows VM but the connection fails (timeout, refused, or error dialog).

### Symptoms → Solutions

| Symptom                                                                     | Solution                                                   | Documentation                                                                                                                                                                            |
| --------------------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Connection times out, no response at all                                    | NSG missing allow rule for port 3389                       | [NSG blocking RDP](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-nsg-problem)                                                           |
| Connection times out, NSG rules look correct                                | Guest OS firewall is blocking inbound RDP                  | [Guest OS firewall blocking](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/guest-os-firewall-blocking-inbound-traffic)                                   |
| "Your credentials did not work"                                             | Wrong password or username format                          | [Credentials error](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#windows-security-error-your-credentials-did-not-work) |
| "An internal error has occurred"                                            | RDP service, TLS certificate, or security layer issue      | [RDP internal error](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-internal-error)                                                      |
| Black screen after login                                                    | Explorer.exe crash, GPU driver, or GPO stuck               | [Black screen troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-black-screen)                                              |
| "No Remote Desktop License Servers available"                               | RDS licensing grace period expired                         | [Specific RDP errors](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#rdplicense)                                         |
| "Remote Desktop can't find the computer"                                    | VM has no public IP, DNS issue, or VM is deallocated       | [Specific RDP errors](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#rdpname)                                            |
| "An authentication error has occurred / LSA"                                | NLA/CredSSP mismatch, clock skew, or wrong username format | [Specific RDP errors](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#rdpauth)                                            |
| "Remote Desktop can't connect to the remote computer"                       | Generic — multiple possible causes                         | [Specific RDP errors](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#rdpconnect)                                         |
| "Because of a security error"                                               | TLS certificate or version mismatch                        | [RDP general error](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-general-error)                                                        |
| RDP connects then disconnects immediately                                   | Session limits, idle timeout, or resource exhaustion       | [RDP disconnections](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-connection)                                                          |
| Works from some IPs but not others                                          | NSG source IP restriction too narrow                       | [NSG blocking RDP](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-nsg-problem)                                                           |
| Event log shows specific RDP error Event IDs                                | Match Event ID to known cause (e.g., 1058, 36870)          | [RDP issues by Event ID](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/event-id-troubleshoot-vm-rdp-connecton)                                           |
| "Authentication error has occurred" / "function requested is not supported" | CredSSP, NLA, or certificate issue                         | [Authentication errors on RDP](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/cannot-connect-rdp-azure-vm)                                                |
| Guest NIC is disabled inside the VM                                         | Enable NIC via Run Command or Serial Console               | [Troubleshoot RDP — NIC disabled](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-nic-disabled)                                           |

### Quick Commands — RDP

```bash
# Check VM power state
az vm get-instance-view --name <vm-name> -g <resource-group> \
  --query "instanceView.statuses[1].displayStatus" -o tsv

# Check NSG rules
az network nsg rule list --nsg-name <nsg-name> -g <resource-group> -o table

# Reset RDP configuration to defaults (re-enables RDP, resets port, restarts TermService)
az vm user reset-remote-desktop --name <vm-name> -g <resource-group>

# Reset VM password
az vm user update --name <vm-name> -g <resource-group> -u <username> -p '<new-password>'

# IP Flow Verify — test if NSG allows traffic
az network watcher test-ip-flow --direction Inbound --protocol TCP \
  --local <vm-private-ip>:3389 --remote <your-public-ip>:* \
  --vm <vm-name> -g <resource-group>
```

### General RDP Troubleshooting

If the symptom doesn't match a specific row above, follow Microsoft's systematic approach:

- [Troubleshoot RDP connections to an Azure VM](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-connection)
- [Detailed RDP troubleshooting steps](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/detailed-troubleshoot-rdp)

---

## Unable to SSH into the VM

User is trying to SSH into a Linux VM but the connection fails.

### Symptoms → Solutions

| Symptom                                           | Solution                                                                                   | Documentation                                                                                                                                    |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| "Connection refused" on port 22                   | SSH service not running or listening on a different port                                   | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)           |
| "Connection timed out"                            | NSG blocking port 22, VM not running, or no public IP                                      | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)           |
| "Permission denied (publickey)"                   | Wrong SSH key, wrong user, or key not in authorized_keys                                   | [Detailed SSH troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/detailed-troubleshoot-ssh-connection) |
| "Permission denied (password)"                    | Wrong password or password auth disabled in sshd_config                                    | [Detailed SSH troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/detailed-troubleshoot-ssh-connection) |
| "Host key verification failed"                    | VM was redeployed and got a new host key                                                   | Remove old entry from `~/.ssh/known_hosts`                                                                                                       |
| "Server unexpectedly closed connection"           | Disk full, SSH config error, or PAM issue                                                  | [Detailed SSH troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/detailed-troubleshoot-ssh-connection) |
| SSH hangs with no response                        | Firewall (iptables/firewalld), routing, or NIC issue                                       | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)           |
| Cannot SSH into Debian Linux VM                   | Debian-specific network or sshd config issue                                               | [Cannot connect to Debian Linux VM](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/cannot-connect-debian-linux)     |
| SSH blocked after SELinux policy change           | SELinux misconfigured — blocking sshd                                                      | [SELinux troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/linux-selinux-troubleshooting)             |
| "Permission denied" with Entra ID (AAD) SSH login | Missing role assignment: Virtual Machine Administrator Login or Virtual Machine User Login | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)           |
| Linux VM not booting — UEFI boot failure          | Gen2 VM UEFI boot issue preventing SSH                                                     | [Linux VM UEFI boot failures](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/azure-linux-vm-uefi-boot-failures)     |

### Quick Commands — SSH

```bash
# Reset SSH configuration to defaults (resets sshd_config, restarts sshd)
az vm user reset-ssh --name <vm-name> -g <resource-group>

# Reset SSH public key for a user
az vm user update --name <vm-name> -g <resource-group> \
  -u <username> --ssh-key-value "<ssh-public-key>"

# Reset password for Linux VM
az vm user update --name <vm-name> -g <resource-group> \
  -u <username> -p '<new-password>'

# Check if sshd is running via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript --scripts "systemctl status sshd"

# Check SELinux status via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript --scripts "getenforce"

# Set SELinux to permissive mode (temporary — survives until reboot)
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript --scripts "setenforce 0"
```

### General SSH Troubleshooting

If the symptom doesn't match a specific row above, follow Microsoft's systematic approach:

- [Troubleshoot SSH connections to an Azure Linux VM](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)
- [Detailed SSH troubleshooting steps](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/detailed-troubleshoot-ssh-connection)

---

## Network Connectivity Problems

User's VM is running but unreachable due to network-level issues (NSG, routing, NIC, DNS).

### Symptoms → Solutions

| Symptom                                   | Solution                                                | Documentation                                                                                                                                  |
| ----------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| NSG has no allow rule for RDP/SSH port    | Add inbound allow rule for TCP 3389 or 22               | [NSG blocking RDP](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-nsg-problem)                 |
| NSG at both NIC and subnet level blocking | Traffic must pass both NSGs — check effective rules     | [Diagnose VM traffic filtering](https://learn.microsoft.com/en-us/azure/network-watcher/diagnose-vm-network-traffic-filtering-problem)         |
| Custom route (UDR) sending traffic to NVA | Check effective routes, verify NVA is forwarding        | [Diagnose VM routing](https://learn.microsoft.com/en-us/azure/network-watcher/diagnose-vm-network-routing-problem)                             |
| VM has no public IP                       | Add a public IP or connect via Azure Bastion            | [Public IP addresses](https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/public-ip-addresses)                                 |
| NIC is disabled inside guest OS (Windows) | Enable NIC via Run Command or Serial Console            | [Troubleshoot RDP — NIC disabled](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-nic-disabled) |
| Static IP misconfiguration inside guest   | Azure VMs should use DHCP; reset NIC to restore         | [Reset network interface](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-network-interface)               |
| Ghost NIC after disk swap or resize       | Old NIC holds IP config, new NIC can't get IP           | [Reset network interface](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-network-interface)               |
| DNS resolution failure                    | Check DNS server config; Azure default is 168.63.129.16 | [DHCP troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-dhcp-failed-to-configure)    |

### Quick Commands — Network

```bash
# Reset NIC (restores DHCP, removes stale config)
az vm repair reset-nic --name <vm-name> -g <resource-group> --yes

# Check effective NSG rules on a NIC
az network nic list-effective-nsg --name <nic-name> -g <resource-group>

# Check effective routes
az network nic show-effective-route-table --name <nic-name> -g <resource-group> -o table

# Check if VM has a public IP
az vm list-ip-addresses --name <vm-name> -g <resource-group> -o table

# Test connectivity from VM to a destination
az network watcher test-connectivity --source-resource <vm-resource-id> \
  --dest-address <destination-ip> --dest-port 3389 -g <resource-group>
```

---

## Firewall Blocking Connectivity

Guest OS firewall (Windows Firewall or Linux iptables/firewalld) is blocking inbound connections even though NSG allows them.

### Symptoms → Solutions

| Symptom                                           | Solution                                             | Documentation                                                                                                                                          |
| ------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Windows Firewall blocking RDP                     | Re-enable "Remote Desktop" firewall rule group       | [Guest OS firewall blocking](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/guest-os-firewall-blocking-inbound-traffic) |
| Firewall policy set to BlockInboundAlways         | Reset to `blockinbound,allowoutbound` policy         | [Enable/disable firewall rule](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/enable-disable-firewall-rule-guest-os)    |
| Third-party AV/firewall blocking                  | Stop the third-party service, test, then reconfigure | [Guest OS firewall blocking](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/guest-os-firewall-blocking-inbound-traffic) |
| Linux iptables/firewalld blocking SSH             | Add allow rule for port 22                           | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)                 |
| Cannot access firewall settings (no connectivity) | Use offline repair VM to modify registry             | [Disable guest OS firewall offline](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/disable-guest-os-firewall-windows)   |

### Quick Commands — Firewall

```bash
# Reset RDP config (re-enables RDP, creates firewall rule for 3389)
az vm user reset-remote-desktop --name <vm-name> -g <resource-group>

# Query Windows Firewall rules via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunPowerShellScript \
  --scripts "netsh advfirewall firewall show rule name='Remote Desktop - User Mode (TCP-In)'"

# Enable Remote Desktop firewall rule via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunPowerShellScript \
  --scripts "netsh advfirewall firewall set rule group='Remote Desktop' new enable=yes"
```

---

## VM Agent Not Responding

Run Command and password reset depend on the VM agent. If the agent is unhealthy, alternative methods are needed.

### Symptoms → Solutions

| Symptom                                                          | Solution                                                 | Documentation                                                                                                                                                       |
| ---------------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Run Command times out                                            | VM agent may be down — use Serial Console instead        | [Serial Console overview](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/serial-console-overview)                                    |
| Password reset fails via Portal/CLI                              | VMAccess extension can't communicate — use offline reset | [Reset password without agent](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-local-password-without-agent)                    |
| VM not booting (Boot Diagnostics shows BSOD/stuck)               | OS-level issue — use repair VM for offline fix           | [Repair VM commands](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/repair-windows-vm-using-azure-virtual-machine-repair-commands)   |
| VMAccess extension error on domain controller                    | VMAccess doesn't support DCs — use Serial Console        | [Serial Console overview](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/serial-console-overview)                                    |
| VM agent not responding on Linux VM                              | Use Serial Console for Linux to access the VM            | [Serial Console for Linux](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/serial-console-linux-overview)                               |
| Linux VM not booting (Boot Diagnostics shows kernel panic/stuck) | Use repair VM for offline Linux disk fix                 | [Repair Linux VM commands](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/repair-linux-vm-using-azure-virtual-machine-repair-commands) |

### Quick Commands — Diagnostic Tools

```bash
# Connect to Serial Console via CLI
az serial-console connect --name <vm-name> -g <resource-group>

# Enable boot diagnostics (required for Serial Console)
az vm boot-diagnostics enable --name <vm-name> -g <resource-group>

# Get boot diagnostics screenshot/log
az vm boot-diagnostics get-boot-log --name <vm-name> -g <resource-group>

# Create repair VM for offline fixes
az vm repair create --name <vm-name> -g <resource-group> \
  --repair-username repairadmin --repair-password '<password>'

# Restore after offline fix
az vm repair restore --name <vm-name> -g <resource-group>
```

---

## Credential and Authentication Errors

User can reach the VM but authentication fails.

### Symptoms → Solutions

| Symptom                                                    | Solution                                                                      | Documentation                                                                                                                                 |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| "Your credentials did not work"                            | Reset password via Portal or CLI                                              | [Reset RDP service or password](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-rdp)                      |
| "Must change password before logging on"                   | Reset password via Portal (bypasses the requirement)                          | [Reset RDP service or password](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-rdp)                      |
| "This user account has expired"                            | Extend account via Run Command: `net user <user> /expires:never`              | [Reset RDP service or password](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-rdp)                      |
| "Trust relationship between workstation and domain failed" | Reset machine account or rejoin domain                                        | [Troubleshoot RDP connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-connection)      |
| "Access is denied" / "Connection was denied"               | Add user to Remote Desktop Users group                                        | [Specific RDP errors](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#wincred) |
| Wrong username format                                      | Use `VMNAME\user` for local, `DOMAIN\user` for domain accounts                | [Specific RDP errors](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#wincred) |
| CredSSP "encryption oracle" error                          | Temporary: set AllowEncryptionOracle=2 on client; permanent: patch both sides | [CredSSP remediation](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/credssp-encryption-oracle-remediation)    |

### Quick Commands — Credentials

```bash
# Reset password
az vm user update --name <vm-name> -g <resource-group> -u <username> -p '<new-password>'

# Reset RDP configuration (also re-enables NLA)
az vm user reset-remote-desktop --name <vm-name> -g <resource-group>
```

---

## RDP Service and Configuration Issues

VM is reachable but the RDP service itself is broken or misconfigured.

### Symptoms → Solutions

| Symptom                                | Solution                                                               | Documentation                                                                                                                                    |
| -------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| TermService not running                | Start the service and set to Automatic                                 | [Reset RDP service](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-rdp)                                     |
| RDP port changed from 3389             | Reset port or update NSG to allow the custom port                      | [Detailed RDP troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/detailed-troubleshoot-rdp)          |
| RDP disabled (fDenyTSConnections = 1)  | Reset RDP config via CLI or Portal                                     | [Reset RDP service](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-rdp)                                     |
| TLS/SSL certificate expired or corrupt | Delete cert and restart TermService to regenerate                      | [RDP internal error](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-internal-error)              |
| NLA/Security Layer mismatch            | Temporarily disable NLA for recovery                                   | [RDP general error](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-general-error)                |
| GPO overriding local RDP settings      | Check `HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services` | [Detailed RDP troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/detailed-troubleshoot-rdp)          |
| RDS licensing expired                  | Remove RDSH role or configure license server                           | [Specific RDP errors](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#rdplicense) |

### Quick Commands — RDP Service

```bash
# Reset all RDP configuration to defaults
az vm user reset-remote-desktop --name <vm-name> -g <resource-group>

# Check TermService status via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunPowerShellScript --scripts "Get-Service TermService | Select-Object Status, StartType"

# Restart VM (if RDP service is unrecoverable)
az vm restart --name <vm-name> -g <resource-group>

# Redeploy VM (moves to new host — last resort)
az vm redeploy --name <vm-name> -g <resource-group>
```

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