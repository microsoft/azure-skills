# Multi-Rack Networking

Use for network fabric, isolation domains, logical and virtual networks, load balancers, public IPs, NAT gateways, and NSGs on a multi-rack instance.

Multi-rack networking is managed through `Microsoft.ManagedNetworkFabric` and is fundamentally different from standard Azure Local SDN. Do not apply SDN or standard Azure Local network procedures here.

## Concepts

The network fabric is the deployed physical network — racks, switches, terminal server connections, and cabling — represented in Azure as a Network Fabric resource. It provides bootstrapping and lifecycle management of devices, workload network configuration for east-west and north-south traffic, observability, and access policy.

## Intake

| Question | Why it matters |
| --- | --- |
| Confirmed multi-rack? | Standard Azure Local SDN procedures do not apply. |
| Fabric and NFC state | Changes require a healthy fabric control plane. |
| Existing isolation domains | L2/L3 segmentation drives logical network design. |
| North-south requirements | Determines route policy, public IP, and NAT gateway needs. |
| Load balancing requirements | Internal vs public load balancer paths differ. |

## Sequence

1. **Confirm scale and fabric state** — Read-only inventory of fabric, devices, and isolation domains. See [resource-types](../../references/resource-types.md).
2. **Load authoritative docs** — Fetch `multi-rack-network-fabric-overview` via [docs-map](../../references/docs-map.md).
3. **Design segmentation** — Configure L3 isolation domains before dependent logical networks.
4. **Create logical networks** — Then network interfaces for workloads.
5. **Virtual networks** — Where the workload requires them.
6. **Load balancing** — Load balancer logical network first, then internal or public load balancer.
7. **External connectivity** — Public IP and NAT gateway as required.
8. **Security** — Create and manage network security groups.
9. **Validate** — Confirm reachability and that route import/export behaves as intended.

## Guardrails

- Fabric and isolation domain changes are instance-wide. Always confirm with the user first.
- Do not modify route policies without understanding existing import/export behavior.
- Do not delete a logical network or isolation domain still referenced by workloads.
- Never treat Azure Resource Health as fabric health.
- Follow [safety-rules](../../references/safety-rules.md).

## Evidence to collect

- Network Fabric Controller and fabric resource IDs and state.
- Network device inventory and health.
- Isolation domain configuration, L2 and L3.
- Logical and virtual network definitions.
- Load balancer, public IP, and NAT gateway configuration.
- NSG rules applied to affected interfaces.

## Related references

- [Docs map](../../references/docs-map.md)
- [CLI and prerequisites](../../references/cli-and-prereqs.md)
- [Resource types](../../references/resource-types.md)
- [Safety rules](../../references/safety-rules.md)
