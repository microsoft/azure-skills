# Tool — Remote MCP server, agent identity / project MI (`type: mcp`)

Attach a remote MCP server that accepts an **Entra ID token minted for a Foundry-managed identity** — no user in the loop, no stored secret. Foundry acquires the token and presents it to the server; you authorize the identity on the target server before the agent invokes it. Needs a **connection** (`--kind remote-tool --auth-type agentic-identity` or `project-managed-identity`) scoped to the upstream resource via `--audience`; the toolbox references it by name and the created tool carries a populated `project_connection_id`.

Use this when the MCP server accepts an **app-only** service-principal token (not a user's) — e.g. the Microsoft-hosted Azure Language MCP, or your own Azure Functions MCP behind Easy Auth. For per-user identity instead, see [tool-mcp-user-entra-token.md](tool-mcp-user-entra-token.md).

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

## Pick the sub-type

| Sub-type | `--auth-type` | Stored `authType` | Identity used |
|---|---|---|---|
| **Agent Identity** | `agentic-identity` | `AgenticIdentityToken` | the **agent's own** managed identity (unique per published agent) |
| **Project Managed Identity** | `project-managed-identity` | `ProjectManagedIdentity` | the **shared project** managed identity (all agents share it) |

> **Agent identity resolves only inside a published agent.** A standalone `tools/list` against the toolbox returns `AgenticIdentityToken ... requires AgentInstanceClientId` — the token is minted only when a **deployed, published agent** invokes the toolbox. Project managed identity resolves without an agent, so use it to test the wiring first.

The **audience** is the Entra resource the target server validates the token against (`aud` must match). Where it comes from depends on the server:

- **Microsoft-hosted** (e.g. Azure Language MCP) → a well-known value from the server's docs, e.g. `https://cognitiveservices.azure.com/`. Authorize by granting the identity an **RBAC role** on the target resource.
- **Your own server** (e.g. Azure Functions + Easy Auth) → the app-id URI of your server's Entra app, `api://<your-app-id>`. Authorize by **allow-listing** the identity's client ID. Probe an unknown audience: `curl -s -i https://<server>/mcp -X POST -d '{}' | grep -i www-authenticate`.

---

# A. Imperative CLI

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Agent identity is minted only for a **published** agent, so you create the connection + toolbox, deploy the agent, **then** authorize the identity.

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# 1. Create the connection (pick the --auth-type for your sub-type; pass your server's audience)
azd ai connection create langmcpconn \
  --kind remote-tool \
  --target "https://<language-service>.cognitiveservices.azure.com/language/mcp?api-version=2025-11-15-preview" \
  --auth-type agentic-identity \
  --audience "https://cognitiveservices.azure.com/" \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
# Project Managed Identity — swap the auth-type:  --auth-type project-managed-identity
# Your own server — set --target to your MCP endpoint and --audience to api://<your-app-id>

# Write the toolbox spec to a file
cat > lang-mcp.yaml <<'EOF'
description: agent-identity mcp toolbox
connections:
  - name: langmcpconn
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file lang-mcp.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> `azd ai toolbox create` / `delete` require an **azd environment** (run inside an `azd init`'d directory), unlike `connection create` / `toolbox show` which work with just `--project-endpoint`.

**Add to an existing toolbox** (new version — then promote):

```bash
azd ai toolbox connection add agent-tools langmcpconn --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
azd ai toolbox publish agent-tools <new-version> --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

## Authorize the identity (after the agent is published)

Deploy the agent (`azd deploy agent-tools` / `azd up`) so its identity exists, then get its IDs:

```bash
# Project managed identity → the Foundry account's system-assigned identity
PRINCIPAL=$(az cognitiveservices account show -n <foundry-account> -g <rg> --query "identity.principalId" -o tsv)
APP_ID=$(az ad sp show --id "$PRINCIPAL" --query appId -o tsv)   # its app (client) ID

# Agent identity → SPs named "...-AgentIdentity"; list and pick your agent's:
az ad sp list --all --query "[?ends_with(displayName,'-AgentIdentity')].{name:displayName, appId:appId}" -o table
```

**Microsoft-hosted server** — grant the identity an **RBAC role** on the target resource:

```bash
az role assignment create --assignee "$PRINCIPAL" \
  --role "Cognitive Services User" \
  --scope "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<language-service>"
```

**Your own server** — add the identity's **client ID** to the server's Easy Auth allow-list (`allowedApplications`) alongside `allowedAudiences: ["api://<app-id>", "<app-id>"]` and issuer `https://login.microsoftonline.com/<tenant>/v2.0`, via `az rest --method put .../config/authsettingsV2?api-version=2022-03-01`. Use the **agent identity** app ID for `AgenticIdentityToken`, or the **project resource** app ID for `ProjectManagedIdentity`.

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service; `azd up` provisions, deploys, and **publishes the agent** (whose identity you then authorize above). Create the connection first (section A, step 1), then reference it by **name** via `project_connection_id`.

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: mcp
        server_label: language-mcp
        project_connection_id: langmcpconn   # the connection name from section A
  my-agent:
    host: azure.ai.agent
    uses:
      - agent-tools
    environmentVariables:
      - name: TOOLBOX_NAME
        value: agent-tools
```

```bash
azd up   # provision + deploy + publish the agent, then authorize the identity (section A)
```

Set **`FOUNDRY_PROJECT_ENDPOINT` and `AZURE_SUBSCRIPTION_ID`** in the azd env before `azd up`. Both sub-types are app-only; no `--client-id` / `--client-secret`.

---

## Verify

Agent identity is minted only inside a **published** agent — you can't validate it with a standalone `tools/list`. Deploy the agent, confirm its `TOOLBOX_ENDPOINT` points at the toolbox, then invoke it:

```bash
azd ai agent invoke <agent-name> "Use the <tool> to ..."
```

Test project-managed-identity wiring first (it resolves without an agent). Troubleshooting:

| Symptom | Cause / fix |
|---|---|
| `AgenticIdentityToken ... requires AgentInstanceClientId` on `tools/list` | Agent identity resolves only inside a **published agent** — invoke through a deployed agent, or test with **project managed identity** first. |
| `401` from the server | Token *rejected* — audience, issuer, or allow-list mismatch. Confirm the server's **audience** matches `--audience`, the **issuer** is your tenant's v2 endpoint, and the identity's **client ID is allow-listed**. |
| `403` from the server | Token *accepted* but the identity lacks permission — grant the required **RBAC role** (Microsoft-hosted), or fix `allowedApplications` (your own server). |

## References

- [MCP tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/model-context-protocol)
- [Azure Language MCP server](https://learn.microsoft.com/azure/ai-services/language-service/concepts/foundry-tools-agents)
- [tool-mcp-user-entra-token.md](tool-mcp-user-entra-token.md) — per-user identity variant
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
