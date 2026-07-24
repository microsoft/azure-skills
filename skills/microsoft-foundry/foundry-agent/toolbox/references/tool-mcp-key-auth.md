# Tool — Remote MCP server, static key (`type: mcp`)

Attach a remote MCP server that authenticates with a **static key** (e.g. a GitHub PAT passed as a Bearer token) to a toolbox. This needs a **connection** (`--kind remote-tool --auth-type custom-keys`) — the toolbox references it by name and the created toolbox tool carries a populated `project_connection_id`. The key is stored on the connection, never in the toolbox spec.

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

---

# A. Imperative CLI

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# 1. Create the static-key connection (the key lives on the connection)
azd ai connection create github-mcp-conn \
  --kind remote-tool --target https://api.githubcopilot.com/mcp \
  --auth-type custom-keys --custom-key Authorization="Bearer $GITHUB_PAT" \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"

# Write the toolbox spec to a file
cat > github-mcp.yaml <<'EOF'
description: github-mcp toolbox
connections:
  - name: github-mcp-conn
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create github-tools --from-file github-mcp.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> `azd ai toolbox create` / `delete` require an **azd environment** (run inside an `azd init`'d directory), unlike `connection create` / `toolbox show` which work with just `--project-endpoint`.

**Add to an existing toolbox** (new version — then promote):

```bash
azd ai toolbox connection add github-tools github-mcp-conn --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
azd ai toolbox publish github-tools <new-version> --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

`connection add` creates a new immutable version but leaves the default unchanged until you `publish` it.

`--from-file` entry:

```yaml
connections:
  - name: github-mcp-conn      # RemoteTool — just the name; the static key lives on the connection
```

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service in `azure.yaml`; `azd deploy` upserts it (and auto-promotes the new version). Create the static-key connection first (section A, step 1), then reference it under `tools:` by its **name** via `project_connection_id`.

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: mcp
        server_label: github
        project_connection_id: github-mcp-conn   # the connection name from section A
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
- Authed MCP servers (static key, OAuth, agent identity, Entra passthrough) all use `project_connection_id: <connection-name>`; no-auth servers use inline `server_url`.

The agent references the toolbox **by name** (`TOOLBOX_NAME`), so the MCP endpoint resolves at runtime — no endpoint string is hard-coded. See [use-toolbox-in-hosted-agent.md](../../create/references/use-toolbox-in-hosted-agent.md).

---

## Verify & deploy

After creating the toolbox either way, verify its MCP endpoint end-to-end (bearer token + raw `tools/list` / `tools/call`) — see [test-endpoint.md](test-endpoint.md).

---

## References

- [GitHub MCP server](https://github.com/github/github-mcp-server) — the static-key example used above
- [MCP tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/mcp)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
