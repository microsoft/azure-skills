# Firewall Blocking Connectivity

Guest OS firewall (Windows Firewall or Linux iptables/firewalld) is blocking inbound connections even though NSG allows them.

## Symptoms → Solutions

| Symptom                                                     | OS      | Solution                                             | Documentation                                                                                                                                          |
| ----------------------------------------------------------- | ------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Windows Firewall blocking RDP                               | Windows | Re-enable "Remote Desktop" firewall rule group       | [Guest OS firewall blocking](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/guest-os-firewall-blocking-inbound-traffic) |
| Firewall policy set to BlockInboundAlways                   | Windows | Reset to `blockinbound,allowoutbound` policy         | [Enable/disable firewall rule](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/enable-disable-firewall-rule-guest-os)    |
| Third-party AV/firewall blocking                            | Windows | Stop the third-party service, test, then reconfigure | [Guest OS firewall blocking](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/guest-os-firewall-blocking-inbound-traffic) |
| iptables/nftables blocking SSH (port 22)                    | Linux   | Add allow rule or flush blocking chain               | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)                 |
| firewalld blocking SSH                                      | Linux   | Open port 22 in the active zone                      | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)                 |
| UFW blocking SSH (Ubuntu/Debian)                            | Linux   | Run `ufw allow 22/tcp` or disable UFW temporarily    | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)                 |
| Cannot access firewall settings — no connectivity (Windows) | Windows | Use offline repair VM to modify registry             | [Disable guest OS firewall offline](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/disable-guest-os-firewall-windows)   |
| Cannot access firewall settings — no connectivity (Linux)   | Linux   | Use Serial Console or repair VM to edit iptables/firewalld config | [Repair Linux VM commands](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/repair-linux-vm-using-azure-virtual-machine-repair-commands) |

## Quick Commands — Windows

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

## Quick Commands — Linux

```bash
# Check iptables rules via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript --scripts "iptables -L -n --line-numbers"

# Allow SSH through iptables via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript --scripts "iptables -I INPUT -p tcp --dport 22 -j ACCEPT"

# Check firewalld status and open SSH via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript \
  --scripts "firewall-cmd --state && firewall-cmd --add-service=ssh --permanent && firewall-cmd --reload"

# Check/allow UFW (Ubuntu/Debian) via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript --scripts "ufw status; ufw allow 22/tcp"
```
