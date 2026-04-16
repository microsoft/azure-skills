# Unable to RDP into the VM

User is trying to RDP into a Windows VM but the connection fails (timeout, refused, or error dialog).

## Symptoms → Solutions

| Symptom                                                                     | Solution                                                   | Documentation                                                                                                                                                                            |
| --------------------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Connection times out, no response at all                                    | NSG missing allow rule for port 3389                       | [NSG blocking RDP](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-nsg-problem)                                                           |
| Connection times out, NSG rules look correct                                | Guest OS firewall is blocking inbound RDP                  | [Guest OS firewall blocking](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/guest-os-firewall-blocking-inbound-traffic)                                   |
| "Your credentials did not work"                                             | Wrong password or username format                          | [Credentials error](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#windows-security-error-your-credentials-did-not-work) |
| "An internal error has occurred"                                            | RDP service, TLS certificate, or security layer issue      | [RDP internal error](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-internal-error)                                                      |
| Black screen after login                                                    | Explorer.exe crash, GPU driver, or GPO stuck               | [Detailed RDP troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/detailed-troubleshoot-rdp)                                                  |
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

## Quick Commands

> ⚠️ **Warning:** Commands marked with ⚡ use the VM agent/extensions. Run [Pre-Flight Safety Checks](cannot-connect-to-vm.md#pre-flight-safety-checks) before using them.

```bash
# Check VM power state
az vm get-instance-view --name <vm-name> -g <resource-group> \
  --query "instanceView.statuses[1].displayStatus" -o tsv

# Check NSG rules
az network nsg rule list --nsg-name <nsg-name> -g <resource-group> -o table

# ⚡ Reset RDP configuration to defaults (re-enables RDP, resets port, restarts TermService)
az vm user reset-remote-desktop --name <vm-name> -g <resource-group>

# ⚡ Reset VM password
az vm user update --name <vm-name> -g <resource-group> -u <username> -p '<new-password>'

# IP Flow Verify — test if NSG allows traffic
az network watcher test-ip-flow --direction Inbound --protocol TCP \
  --local <vm-private-ip>:3389 --remote <your-public-ip>:* \
  --vm <vm-name> -g <resource-group>
```

## General RDP Troubleshooting

If the symptom doesn't match a specific row above, follow Microsoft's systematic approach:

- [Troubleshoot RDP connections to an Azure VM](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-connection)
- [Detailed RDP troubleshooting steps](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/detailed-troubleshoot-rdp)
