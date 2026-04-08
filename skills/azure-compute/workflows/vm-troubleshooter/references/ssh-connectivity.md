# Unable to SSH into the VM

User is trying to SSH into a Linux VM but the connection fails.

## Symptoms → Solutions

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

## Quick Commands

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

## General SSH Troubleshooting

If the symptom doesn't match a specific row above, follow Microsoft's systematic approach:

- [Troubleshoot SSH connections to an Azure Linux VM](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)
- [Detailed SSH troubleshooting steps](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/detailed-troubleshoot-ssh-connection)
