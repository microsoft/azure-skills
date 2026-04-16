# Credential and Authentication Errors

User can reach the VM but authentication fails.

## Windows (RDP) — Symptoms → Solutions

| Symptom                                                    | Solution                                                                      | Documentation                                                                                                                                 |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| "Your credentials did not work"                            | Reset password via Portal or CLI                                              | [Reset RDP service or password](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-rdp)                      |
| "Must change password before logging on"                   | Reset password via Portal (bypasses the requirement)                          | [Reset RDP service or password](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-rdp)                      |
| "This user account has expired"                            | Extend account via Run Command: `net user <user> /expires:never`              | [Reset RDP service or password](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-rdp)                      |
| "Trust relationship between workstation and domain failed" | Reset machine account or rejoin domain                                        | [Troubleshoot RDP connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-connection)      |
| "Access is denied" / "Connection was denied"               | Add user to Remote Desktop Users group                                        | [Specific RDP errors](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#wincred) |
| Wrong username format                                      | Use `VMNAME\user` for local, `DOMAIN\user` for domain accounts                | [Specific RDP errors](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-specific-rdp-errors#wincred) |
| CredSSP "encryption oracle" error                          | Temporary: set AllowEncryptionOracle=2 on client; permanent: patch both sides | [CredSSP remediation](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/credssp-encryption-oracle-remediation)    |

## Linux (SSH) — Symptoms → Solutions

| Symptom                                                     | Solution                                                                      | Documentation                                                                                                                                    |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| "Permission denied (publickey)"                             | Wrong key, wrong user, or key not in authorized_keys — reset key via CLI      | [Detailed SSH troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/detailed-troubleshoot-ssh-connection) |
| "Permission denied (password)"                              | Wrong password or password auth disabled in sshd_config                        | [Detailed SSH troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/detailed-troubleshoot-ssh-connection) |
| Account locked after failed attempts                        | Unlock via Run Command: `passwd -u <user>` or `pam_tally2 --reset --user <user>` | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)           |
| "Permission denied" with Entra ID (AAD) SSH login           | Missing role: Virtual Machine Administrator Login or Virtual Machine User Login | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)           |
| sudo password prompt fails / user not in sudoers            | Fix via Run Command or Serial Console                                          | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)           |

## Quick Commands — Windows

> ⚠️ **Warning:** Commands below use the VM agent/extensions. Run [Pre-Flight Safety Checks](cannot-connect-to-vm.md#pre-flight-safety-checks) before using them.

```bash
# ⚡ Reset password
az vm user update --name <vm-name> -g <resource-group> -u <username> -p '<new-password>'

# ⚡ Reset RDP configuration (also re-enables NLA)
az vm user reset-remote-desktop --name <vm-name> -g <resource-group>
```

## Quick Commands — Linux

> ⚠️ **Warning:** Commands below use the VM agent/extensions. Run [Pre-Flight Safety Checks](cannot-connect-to-vm.md#pre-flight-safety-checks) before using them.

```bash
# ⚡ Reset SSH public key
az vm user update --name <vm-name> -g <resource-group> \
  -u <username> --ssh-key-value "<ssh-public-key>"

# ⚡ Reset password for Linux VM
az vm user update --name <vm-name> -g <resource-group> \
  -u <username> -p '<new-password>'

# ⚡ Unlock a locked account via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript --scripts "passwd -u <username>"
```
