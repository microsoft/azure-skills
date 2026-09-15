# CLI Extensions and Prerequisites

Multi-rack uses a different control plane from standard Azure Local. Verify extensions and prerequisites before generating commands.

## Required CLI extensions

| Extension | Command surface | Provider |
| --- | --- | --- |
| `networkcloud` | `az networkcloud` | `Microsoft.NetworkCloud` |
| `managednetworkfabric` | `az networkfabric` | `Microsoft.ManagedNetworkFabric` |
| `stack-hci-vm` | `az stack-hci-vm` | `Microsoft.AzureStackHCI` |

Install or upgrade:

```azurecli
az extension add --yes --upgrade --name networkcloud
az extension add --yes --upgrade --name managednetworkfabric
az extension add --yes --upgrade --name stack-hci-vm
```

Supporting extensions used by multi-rack include `customlocation`, `k8s-extension`, `k8s-configuration`, and `connectedmachine`. Confirm the current full list from the `multi-rack-cli-extensions` article rather than assuming this set is complete.

Note the naming mismatch: the `managednetworkfabric` extension provides the `az networkfabric` command group.

## Control-plane prerequisites

A multi-rack instance depends on two Azure resources created **before** the cluster:

1. **Network Fabric Controller (NFC)** — the managed control plane for the network fabric.
2. **Cluster Manager (CM)** — paired with the NFC in the same Azure region and subscription.

Each NFC is associated with a CM in the same region. Subsequent multi-rack deployments reuse the pair until the supported cluster quota is reached, at which point a new NFC/CM pair is required.

## Resource provider registration

Multi-rack requires a broad provider set, including `Microsoft.NetworkCloud`, `Microsoft.ManagedNetworkFabric`, `Microsoft.AzureStackHCI`, `Microsoft.ExtendedLocation`, `Microsoft.HybridCompute`, `Microsoft.HybridContainerService`, `Microsoft.ResourceConnector`, and `Microsoft.Kubernetes`.

Fetch the complete list from the `multi-rack-prerequisites` article and register with:

```azurecli
az provider register --namespace <namespace>
```

Do not treat this summary as the authoritative list.

## Command safety

- Generate read-only commands first (`show`, `list`).
- Scope commands to the subscription, resource group, and resource ID.
- Confirm the extension is installed before proposing a command; a missing extension produces a confusing "command not found" rather than a permissions error.
- Ask before any fabric, isolation domain, SAN, or VM power/delete operation.
- Never embed secrets; use Key Vault or interactive authentication.
