# Tool — Fabric IQ (`type: fabric_iq_preview`) — preview

Microsoft Fabric data (**Ontology** / **Fabric data agent** / **Power BI semantic model**) via Fabric IQ. Fabric IQ is exposed as an **MCP-style tool**: a flat tool entry carrying a `server_url` (the Fabric MCP endpoint for your artifact) + a `project_connection_id`. The workspace / ontology / artifact ids live in the **connection's target URL**, not the tool. Auth is a Fabric OAuth connection and requires **tenant admin consent**. For the toolbox concept, versions, and endpoint, see [toolbox.md](../toolbox.md).

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

---

## Prerequisite — a Fabric artifact + connection

1. **Tenant admin consent** for the Fabric IQ OAuth app before any user can invoke the tool.
2. A Microsoft Fabric artifact — an **Ontology**, **Fabric data agent**, or **Power BI semantic model** — in a workspace you can reach.
3. A **`RemoteTool`** connection on the project pointing at that artifact's Fabric MCP endpoint. The endpoint encodes the workspace + artifact ids, e.g. for an ontology:
   `https://<fabric-host>/v1/mcp/dataPlane/workspaces/{workspaceObjectId}/items/{artifactObjectId}/ontologyEndpoint`

   Auth is `user-entra-token` (Entra pass-through, the catalog default) with the Fabric audience, or `oauth2` for a custom app:

   ```bash
   # Entra pass-through (catalog default)
   azd ai connection create fabric-iq-conn \
     --kind remote-tool \
     --target "<fabric-mcp-endpoint>" \
     --auth-type user-entra-token --audience "<fabric-audience>"
   ```

The tool references this connection by `project_connection_id`, and its `server_url` is the same endpoint (the connection's target).

---

# A. Imperative CLI

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# Write the toolbox spec to a file
cat > fiq.yaml <<'EOF'
description: fabric iq toolbox
tools:
  - type: fabric_iq_preview
    name: fabric
    server_label: fabric
    project_connection_id: fabric-iq-conn          # the RemoteTool connection
    server_url: <fabric-mcp-endpoint>              # same endpoint as the connection target
    require_approval: never
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file fiq.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

Fabric IQ is a **flat MCP-style** tool entry — `server_url` + `project_connection_id` are siblings of `type` (not nested under a `fabric_iq_preview: {...}` object, and not a top-level `connections:` array).

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service in `azure.yaml`; `azd deploy` upserts it (and auto-promotes the new version). Needs only an **existing** Foundry project (via `FOUNDRY_PROJECT_ENDPOINT` + `AZURE_SUBSCRIPTION_ID` in the azd env) — **no `azd provision`**, no `infra:` block. The `RemoteTool` connection must already exist (see prerequisite).

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: fabric_iq_preview
        name: fabric
        server_label: fabric
        project_connection_id: fabric-iq-conn
        server_url: <fabric-mcp-endpoint>
        require_approval: never

  # A hosted agent in the same project consumes the toolbox by name
  my-agent:
    host: azure.ai.agent
    uses:
      - agent-tools
    environmentVariables:
      - name: TOOLBOX_NAME
        value: agent-tools
```

```bash
azd deploy agent-tools
```

---

## Verify & deploy

After creating the toolbox either way, verify its MCP endpoint end-to-end — see [test-endpoint.md](test-endpoint.md). Fabric IQ resolves its connection at **list** time, so `tools/list` requires a valid connection (an invalid one returns `Connection resolution failed for '<conn>'`). With a real Fabric connection, `tools/list` surfaces the Fabric MCP sub-tools and `tools/call` queries the artifact.

---

## References

- [Fabric IQ tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
