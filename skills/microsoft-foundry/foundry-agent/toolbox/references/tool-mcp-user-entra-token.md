# Tool — Remote MCP server, user Entra token (`type: mcp`, auth `UserEntraToken`)

Attach a remote MCP server that authenticates with the **caller's own Entra identity** — the platform forwards the signed-in user's Entra token to the MCP server (auth type `UserEntraToken`), so the server sees the **end user**, not a shared credential. No BYO app registration, client secret, or OAuth consent flow. Needs a **connection** (`--kind remote-tool --auth-type user-entra-token`) scoped to the upstream resource via `--audience`; the toolbox references it by name and the created tool carries a populated `project_connection_id`.

Use this when the MCP server enforces per-user permissions off the caller's Entra identity (e.g. Microsoft 365 / Graph-backed services). [Work IQ](tool-work-iq.md) is a concrete, preview instance of this pattern.

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

---

# Getting the catalog inputs

**Only the MCP tiles this query returns support user-entra-token.** Run the discovery script with `--user-entra-token` — it lists exactly the tiles you can attach with this reference, each with the **`audience`** its connection needs:

```bash
../scripts/get-catalog-inputs.sh --user-entra-token      # bash
pwsh ../scripts/get-catalog-inputs.ps1 -UserEntraToken   # PowerShell
```

**If the tile is not in this list, user-entra-token does not apply to it** — it uses a different auth mode.

---

# A. Imperative CLI

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# 1. Create the user-entra-token MCP connection (no secret; audience scopes the forwarded token)
azd ai connection create entra-mcp-conn \
  --kind remote-tool --target https://<mcp-host>/mcp \
  --auth-type user-entra-token \
  --audience <upstream-resource-uri-or-app-id> \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"

# Write the toolbox spec to a file
cat > entra-mcp.yaml <<'EOF'
description: user-entra-token mcp toolbox
connections:
  - name: entra-mcp-conn
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file entra-mcp.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> `azd ai toolbox create` / `delete` require an **azd environment** (run inside an `azd init`'d directory), unlike `connection create` / `toolbox show` which work with just `--project-endpoint`.

**Add to an existing toolbox** (new version — then promote):

```bash
azd ai toolbox connection add agent-tools entra-mcp-conn --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
azd ai toolbox publish agent-tools <new-version> --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

`connection add` creates a new immutable version but leaves the default unchanged until you `publish` it.

`--from-file` entry:

```yaml
connections:
  - name: entra-mcp-conn       # RemoteTool (UserEntraToken); the audience lives on the connection
```

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service; `azd deploy` upserts it (and auto-promotes the new version). Create the user-entra-token connection first (section A, step 1), then reference it under `tools:` by its **name** via `project_connection_id`.

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: mcp
        server_label: entra
        project_connection_id: entra-mcp-conn   # the connection name from section A
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

Set **`FOUNDRY_PROJECT_ENDPOINT` and `AZURE_SUBSCRIPTION_ID`** in the azd env (after it's created) before `azd deploy`, or it errors `infrastructure has not been provisioned`. No `azd provision` / `infra:` block is needed.

---

## Verify & deploy

After creating the toolbox either way, verify its MCP endpoint end-to-end (bearer token + raw `tools/list` / `tools/call`) — see [test-endpoint.md](test-endpoint.md).

> The MCP server resolves data as the **calling user's** Entra identity — there is no separate consent step; the toolbox bearer token's identity is forwarded directly. Locally that's your `az login` identity; through a deployed agent it's the invoking user, so results differ by caller. A caller who lacks access to the upstream resource gets an empty or unauthorized result from that server, not a toolbox error.

---

## References

- [tool-work-iq.md](tool-work-iq.md) — a concrete, verified user-entra-token MCP server (Microsoft 365 Work IQ)
- [MCP tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/mcp)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
