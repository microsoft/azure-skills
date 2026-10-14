# Work IQ

Work IQ is a remote MCP server:

```text
https://workiq.svc.cloud.microsoft/mcp
```

Users need an M365 Copilot license. Attach it directly with an existing Foundry project connection:

```yaml
tools:
  - type: mcp
    server_label: workiq
    server_url: https://workiq.svc.cloud.microsoft/mcp
    project_connection_id: <work-iq-connection>
    require_approval: never
```

Use a connection supplied by the user or already referenced by the Managed Harness Agent. Do not scan for and select an unreferenced connection automatically.

## Explicit connection creation

Only when the user explicitly asks to create the connection, use the default Entra passthrough path:

```bash
azd ai connection create <connection-name> \
  --kind remote-tool \
  --target https://workiq.svc.cloud.microsoft/mcp \
  --auth-type user-entra-token \
  --audience fdcc1f02-fc51-4226-8753-f668596af7f7 \
  --project-endpoint "<project-endpoint>"
```

Validate it with:

```bash
azd ai connection show <connection-name> \
  --project-endpoint "<project-endpoint>"
```

Do not create a Toolbox unless the user explicitly requests one. For that path, follow [Work IQ Toolbox](../../../../toolbox/references/tool-work-iq.md).

Do not author `type: work_iq_preview` in Phase 1; azd recognizes that discriminator but does not model its fields.
