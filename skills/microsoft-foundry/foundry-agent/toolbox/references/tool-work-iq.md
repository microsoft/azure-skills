# Tool — Work IQ (`type: mcp`, preview) — Microsoft 365 work context

Give the agent Microsoft 365 work context (mail, meetings, files, chats, and M365 agents) via the **Work IQ MCP server** at `https://workiq.svc.cloud.microsoft/mcp`. It attaches as a **remote MCP connection** and calls Work IQ as the **signed-in user**, so each user needs an **M365 Copilot license**. For the toolbox concept, versions, and endpoint, see [toolbox.md](../toolbox.md).

- **Server URL:** `https://workiq.svc.cloud.microsoft/mcp`
- **Work IQ API app** (audience / scopes source): `fdcc1f02-fc51-4226-8753-f668596af7f7` ("Work IQ"), delegated scopes `WorkIQAgent.Ask`, `WorkIQAgent.Ask.Selected`, `WorkIQSettings.Read.All`, `WorkIQSettings.ReadWrite.All`.

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

## Two auth paths

Both preserve the caller's M365 identity; pick based on whether you can use Microsoft's managed audience or must bring your own Entra app.

| Path | `--auth-type` | Consent prompt? | When to use |
|---|---|---|---|
| **A. Entra passthrough** | `user-entra-token` + `--audience fdcc1f02-…` | No (for an already-trusted first-party identity) | Simplest — no app registration, no secret. The default. |
| **B. Custom OAuth (BYO app)** | `oauth2` + BYO `client-id`/`secret` | Yes — one-time per user | When your tenant requires you to own the app registration / control the granted scopes. |

Both were verified to return the same **10 Work IQ tools** (`ask`, `search_paths`, `get_schema`, `list_agents`, `fetch`, `call_function`, `do_action`, `create_entity`, `update_entity`, `delete_entity`) and a live `list_agents` result via the caller's identity.

---

# A. Entra passthrough (`user-entra-token`)

The connection carries the Work IQ audience; Foundry passes the caller's Entra identity through. No BYO app, no secret, no consent step.

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# 1. Create the connection (Entra passthrough + Work IQ audience)
azd ai connection create workiq-mcp-conn \
  --kind remote-tool --target https://workiq.svc.cloud.microsoft/mcp \
  --auth-type user-entra-token \
  --audience fdcc1f02-fc51-4226-8753-f668596af7f7 \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"

# 2. Write the toolbox spec to a file, then create the toolbox
cat > workiq.yaml <<'EOF'
description: workiq toolbox
connections:
  - name: workiq-mcp-conn
EOF
azd ai toolbox create agent-tools --from-file workiq.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> `azd ai toolbox create` / `delete` require an **azd environment** (run inside an `azd init`'d directory), unlike `connection create` / `toolbox show` which work with just `--project-endpoint`.

**Add to an existing toolbox** (new version — then promote):

```bash
azd ai toolbox connection add agent-tools workiq-mcp-conn --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
azd ai toolbox publish agent-tools <new-version> --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

Stored shape: `category=RemoteTool, authType=UserEntraToken, audience=fdcc1f02-…, target=.../mcp`.

---

# B. Custom OAuth (BYO Entra app)

Bring your own Entra app granted the `WorkIQAgent.Ask` delegated permission. The mechanics (five OAuth inputs, redirect-URI registration, `-32006` consent gate) are identical to the generic BYO-OAuth2 flow — see [tool-mcp-custom-oauth.md](tool-mcp-custom-oauth.md); the Work IQ specifics are below.

```bash
WORKIQ_APP=fdcc1f02-fc51-4226-8753-f668596af7f7
TENANT=$(az account show --query tenantId -o tsv)

# 1. Create your BYO Entra app + secret, grant it Work IQ's WorkIQAgent.Ask delegated permission
BYO=$(az ad app create --display-name workiq-byo --query appId -o tsv)
SECRET=$(az ad app credential reset --id "$BYO" --query password -o tsv)   # take the LAST line if capturing text
SCOPEID=$(az ad sp show --id "$WORKIQ_APP" --query "oauth2PermissionScopes[?value=='WorkIQAgent.Ask'].id | [0]" -o tsv)
az ad app permission add --id "$BYO" --api "$WORKIQ_APP" --api-permissions "$SCOPEID=Scope"

# 2. Create the custom-OAuth connection (scope must include WorkIQAgent.Ask + offline_access)
azd ai connection create workiq-oauth-conn \
  --kind remote-tool --target https://workiq.svc.cloud.microsoft/mcp \
  --auth-type oauth2 \
  --client-id "$BYO" --client-secret "$SECRET" \
  --authorization-url "https://login.microsoftonline.com/$TENANT/oauth2/v2.0/authorize" \
  --token-url         "https://login.microsoftonline.com/$TENANT/oauth2/v2.0/token" \
  --scopes "api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask offline_access" \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"

# 3. Create the toolbox
cat > workiq-oauth.yaml <<'EOF'
description: workiq oauth toolbox
connections:
  - name: workiq-oauth-conn
EOF
azd ai toolbox create agent-tools --from-file workiq-oauth.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"

# 4. Read the connection's redirect URI and register it on the BYO app
ARM=".../connections/workiq-oauth-conn"   # see tool-mcp-custom-oauth.md for the full ARM path
REDIR=$(az rest --method get --query "properties.redirectUrl" -o tsv \
  --url "https://management.azure.com$ARM?api-version=2025-06-01")
az ad app update --id "$BYO" --web-redirect-uris "$REDIR"
```

The first `tools/list` returns a `-32006` consent URL; the user opens it once, then tools resolve. See [tool-mcp-custom-oauth.md § Set the connector redirect URI](tool-mcp-custom-oauth.md#set-the-connector-redirect-uri-after-the-connection-exists) and [§ Verify](tool-mcp-custom-oauth.md#verify).

---

# Declarative `azure.yaml`

Either connection is referenced under `tools:` by name (create the connection first, per section A or B):

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: mcp
        server_label: workiq
        project_connection_id: workiq-mcp-conn   # or workiq-oauth-conn
        require_approval: never
```

```bash
azd deploy agent-tools
```

Set **`FOUNDRY_PROJECT_ENDPOINT` and `AZURE_SUBSCRIPTION_ID`** in the azd env (after it's created) before `azd deploy`. See [use-toolbox-in-hosted-agent.md](../../create/references/use-toolbox-in-hosted-agent.md).

---

## Verify & deploy

After creating the toolbox, verify its MCP endpoint end-to-end — see [test-endpoint.md](test-endpoint.md).

```bash
ENDPOINT=$(azd ai toolbox show agent-tools --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT" --output json \
  | python -c "import sys,json; print(json.load(sys.stdin)['endpoint'])")
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

# ask — args: question, agentId, fileUrls, conversationId, timeZone
curl -sS -X POST "$ENDPOINT" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"workiq___list_agents","arguments":{}}}' | python -m json.tool
```

> Work IQ resolves data as the **calling user's** M365 identity. Locally that's your `az login` identity; through a deployed agent it's the invoking user — so results differ by caller, and a user without an M365 Copilot license gets no data.

## References

- [Work IQ tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq)
- [MCP server authentication](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication) — Entra identities, OAuth identity passthrough, managed vs custom OAuth
- [tool-mcp-custom-oauth.md](tool-mcp-custom-oauth.md) — the BYO-OAuth2 flow used by path B
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
