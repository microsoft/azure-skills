# Fabric IQ

Connect a Managed Harness Agent to a published Microsoft Fabric Ontology, Fabric data agent, or Power BI semantic model.

```yaml
tools:
  - type: fabric_iq_preview
    server_label: fabric
    server_url: <fabric-mcp-endpoint>
    project_connection_id: <fabric-connection>
    require_approval: never
```

The Fabric MCP endpoint contains the workspace and artifact identifiers. The connection target and `server_url` must refer to the same endpoint.

Use a connection supplied by the user or already referenced by the Agent. Create one only when explicitly requested:

```bash
azd ai connection create <connection-name> \
  --kind remote-tool \
  --target "<fabric-mcp-endpoint>" \
  --auth-type user-entra-token \
  --audience "<fabric-audience>" \
  --project-endpoint "<project-endpoint>"
```

Custom OAuth may be required when the tenant cannot use Entra passthrough. Fabric licensing and tenant admin consent are required, and the Fabric artifact must already be published.

Do not create a Toolbox unless explicitly requested. For that path, follow [Fabric IQ Toolbox](../../../../toolbox/references/tool-fabric-iq.md).
