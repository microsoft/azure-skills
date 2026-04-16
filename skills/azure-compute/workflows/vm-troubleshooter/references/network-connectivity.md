# Network Connectivity Problems

User's VM is running but unreachable due to network-level issues (NSG, routing, NIC, DNS).

> ⚠️ **OS Note:** NSG, routing, and public IP issues are OS-agnostic (Azure platform layer). NIC and DNS issues have OS-specific remediation — see the OS column below.

## Symptoms → Solutions

| Symptom                                    | OS      | Solution                                                | Documentation                                                                                                                                  |
| ------------------------------------------ | ------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| NSG has no allow rule for RDP/SSH port     | Any     | Add inbound allow rule for TCP 3389 or 22               | [NSG blocking RDP](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-nsg-problem)                 |
| NSG at both NIC and subnet level blocking  | Any     | Traffic must pass both NSGs — check effective rules     | [Diagnose VM traffic filtering](https://learn.microsoft.com/en-us/azure/network-watcher/diagnose-vm-network-traffic-filtering-problem)         |
| Custom route (UDR) sending traffic to NVA  | Any     | Check effective routes, verify NVA is forwarding        | [Diagnose VM routing](https://learn.microsoft.com/en-us/azure/network-watcher/diagnose-vm-network-routing-problem)                             |
| VM has no public IP                        | Any     | Add a public IP or connect via Azure Bastion            | [Public IP addresses](https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/public-ip-addresses)                                 |
| NIC is disabled inside guest OS            | Windows | Enable NIC via Run Command or Serial Console            | [Troubleshoot RDP — NIC disabled](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-nic-disabled) |
| NIC is down inside guest OS                | Linux   | Bring interface up via Run Command or Serial Console    | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)          |
| Static IP misconfiguration inside guest    | Windows | Azure VMs should use DHCP; reset NIC to restore         | [Reset network interface](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-network-interface)               |
| Static IP misconfiguration inside guest    | Linux   | Restore DHCP config in `/etc/netplan/` or `/etc/sysconfig/network-scripts/` | [Troubleshoot SSH connection](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection) |
| Ghost NIC after disk swap or resize        | Windows | Old NIC holds IP config, new NIC can't get IP           | [Reset network interface](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/reset-network-interface)               |
| DNS resolution failure                     | Any     | Check DNS server config; Azure default is 168.63.129.16 | [DHCP troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-dhcp-disabled)           |

## Quick Commands — Platform (Any OS)

```bash
# Check effective NSG rules on a NIC
az network nic list-effective-nsg --name <nic-name> -g <resource-group>

# Check effective routes
az network nic show-effective-route-table --name <nic-name> -g <resource-group> -o table

# Check if VM has a public IP
az vm list-ip-addresses --name <vm-name> -g <resource-group> -o table

# Test connectivity from VM to a destination
az network watcher test-connectivity --source-resource <vm-resource-id> \
  --dest-address <destination-ip> --dest-port <port> -g <resource-group>
```

## Quick Commands — Windows

```bash
# Reset NIC (restores DHCP, removes stale config — Windows only)
az vm repair reset-nic --name <vm-name> -g <resource-group> --yes
```

## Quick Commands — Linux

> ⚠️ **Warning:** Commands below use the VM agent/extensions. Run [Pre-Flight Safety Checks](cannot-connect-to-vm.md#pre-flight-safety-checks) before using them.

```bash
# ⚡ Check network interface status via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript --scripts "ip link show; ip addr show"

# ⚡ Bring interface up via Run Command
az vm run-command invoke --name <vm-name> -g <resource-group> \
  --command-id RunShellScript --scripts "ip link set eth0 up && dhclient eth0"
```
