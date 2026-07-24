# Tool — Remote MCP server, no auth (`type: mcp`)

Attach a **public** remote MCP server (no credentials) to a toolbox. A no-auth server still needs a **connection** (`--kind remote-tool --auth-type none`) — the toolbox references it by name and the created toolbox tool carries a populated `project_connection_id`.

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

---

# A. Imperative CLI

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# 1. Create the no-auth connection
azd ai connection create learn-mcp-conn \
  --kind remote-tool --target https://learn.microsoft.com/api/mcp \
  --auth-type none --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"

# Write the toolbox spec to a file
cat > learn-mcp.yaml <<'EOF'
description: learn-mcp toolbox
connections:
  - name: learn-mcp-conn
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create learn-tools --from-file learn-mcp.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> `azd ai toolbox create` / `delete` require an **azd environment** (run inside an `azd init`'d directory), unlike `connection create` / `toolbox show` which work with just `--project-endpoint`.

**Add to an existing toolbox** (new version — then promote):

```bash
azd ai toolbox connection add learn-tools learn-mcp-conn --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
azd ai toolbox publish learn-tools <new-version> --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

`connection add` creates a new immutable version but leaves the default unchanged until you `publish` it.

`--from-file` entry:

```yaml
connections:
  - name: learn-mcp-conn       # RemoteTool — just the name; project_connection_id is populated
```

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service in `azure.yaml`; `azd deploy` upserts it (and auto-promotes the new version). A no-auth MCP server is declared under `tools:` with an inline `server_url` — **no connection needed** on this path.

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    description: learn-mcp toolbox
    tools:
      - type: mcp
        server_label: learn_mcp
        server_url: https://learn.microsoft.com/api/mcp
        require_approval: never

  # A hosted agent in the same project consumes the toolbox by name
  my-agent:
    host: azure.ai.agent
    uses:
      - agent-tools          # depend on the toolbox service
    environmentVariables:
      - name: TOOLBOX_NAME
        value: agent-tools    # agent resolves the MCP endpoint at runtime
```

```bash
azd deploy agent-tools
```

**Requirements & gotchas:**

- Set **`FOUNDRY_PROJECT_ENDPOINT` and `AZURE_SUBSCRIPTION_ID`** in the azd env (after it's created) before `azd deploy`, or it errors `infrastructure has not been provisioned`. No `azd provision` / `infra:` block is needed.

The agent references the toolbox **by name** (`TOOLBOX_NAME`), so the MCP endpoint resolves at runtime — no endpoint string is hard-coded. See [use-toolbox-in-hosted-agent.md](../../create/references/use-toolbox-in-hosted-agent.md).

---

## Verify & deploy

After creating the toolbox either way, verify its MCP endpoint end-to-end (bearer token + raw `tools/list` / `tools/call`) — see [test-endpoint.md](test-endpoint.md).

---

## References

- [Microsoft Learn MCP server](https://learn.microsoft.com/training/support/mcp) — the public example used above
- [MCP tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/mcp)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
