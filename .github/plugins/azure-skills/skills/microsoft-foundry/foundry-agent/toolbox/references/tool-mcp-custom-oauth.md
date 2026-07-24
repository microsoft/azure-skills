# Tool — Remote MCP server, custom OAuth2 app (BYO) (`type: mcp`)

Attach a remote MCP server that authenticates with **your own OAuth2 app** (bring-your-own `client_id` / `client_secret`) — when you own the OAuth app and control the client, scopes, and secret. Either a **third-party / non-Azure MCP** whose OAuth app you register, or a **private MCP on Azure** ([custom MCP on Azure Functions](https://learn.microsoft.com/en-us/azure/foundry/mcp/build-your-own-mcp-server?view=foundry)).

> 🚦 Before creating a toolbox/connection, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

**Flow at a glance** (the redirect URI is chicken-and-egg — OAuth app and connection each need something from the other):
1. **Create the OAuth app** and collect the five inputs — [Getting the OAuth2 inputs](#getting-the-oauth2-inputs). Leave the callback URL as a placeholder.
2. **Create connection + toolbox** — [A. Imperative CLI](#a-imperative-cli) (or [B. Declarative](#b-declarative-azureyaml)).
3. **Register the connection's reply URL** on the OAuth app — [Set the connector redirect URI](#set-the-connector-redirect-uri-after-the-connection-exists).
4. **Verify** — the first `tools/list` returns a one-time consent URL — [Verify](#verify).

---

# Getting the OAuth2 inputs

BYO OAuth2 needs five inputs — `client-id`, `client-secret`, `authorization-url`, `token-url`, `scopes` — feeding the connection in section A. Their source depends on the MCP origin.

## Origin 1 — Third-party / non-Azure MCP (you register the OAuth app)

Hosted elsewhere (SaaS, partner, or your own non-Azure host). Register an OAuth app with **that provider's** identity system and supply all five inputs. Example: a **GitHub OAuth App**.
1. Create the app at **[github.com/settings/applications/new](https://github.com/settings/applications/new)**. Use any name/homepage URL; set **Authorization callback URL** to a placeholder — replace it after the connection exists ([Set the connector redirect URI](#set-the-connector-redirect-uri-after-the-connection-exists)).
2. Copy the **Client ID** and **Generate a new client secret**.
3. Map to connection inputs:

   | Connection input | GitHub OAuth App value |
   |---|---|
   | `--client-id` | **Client ID** |
   | `--client-secret` | the generated **client secret** |
   | `--authorization-url` | `https://github.com/login/oauth/authorize` |
   | `--token-url` | `https://github.com/login/oauth/access_token` |
   | `--scopes` | space-delimited scope(s) your MCP needs — e.g. `read:user` |

Now create the connection (section A), then [Set the connector redirect URI](#set-the-connector-redirect-uri-after-the-connection-exists). Any OAuth2 provider works the same — swap GitHub's endpoint URLs for yours.

## Origin 2 — Azure-hosted MCP you build (starter)

Building your own MCP on Azure Functions? The sample template's `azd up` emits four inputs plus the target; you add a client secret. Recipe: [tool-mcp-custom-oauth-azure-starter.md](tool-mcp-custom-oauth-azure-starter.md).

---

# A. Imperative CLI

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Write the toolbox spec to a **file** — `--from-file` takes a **path** (no stdin `-`). Fill the five inputs from your MCP origin.

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# 1. Create the BYO OAuth2 connection (client secret comes from your MCP's origin, above)
azd ai connection create private-mcp-oauth \
  --kind remote-tool --target https://<mcp-host>/runtime/webhooks/mcp \
  --auth-type oauth2 \
  --client-id <client-id> --client-secret <client-secret> \
  --authorization-url <authorization-url> \
  --token-url         <token-url> \
  --scopes "<scopes>" \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"

# Write the toolbox spec to a file
cat > private-mcp.yaml <<'EOF'
description: private-mcp toolbox (BYO OAuth2)
connections:
  - name: private-mcp-oauth
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create private-tools --from-file private-mcp.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> `toolbox create` / `delete` require an **azd environment** (run inside an `azd init`'d dir). `connection create` and `toolbox create` print a benign `no active azd environment` line even on success — check for the `... created` line, not the warning.

**Add to an existing toolbox** (new version — then promote):

```bash
azd ai toolbox connection add private-tools private-mcp-oauth --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
azd ai toolbox publish private-tools <new-version> --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

`connection add` creates a new immutable version; the default stays unchanged until you `publish`.

## Set the connector redirect URI (after the connection exists)

Foundry generates a **per-connection reply URL** on creation. The OAuth app must whitelist this exact URL, or consent fails with `AADSTS...redirect_uri` mismatch.

**1. Read the reply URL** (`azd ai connection show` doesn't expose it — use the ARM record):

```bash
az rest --method get --query "properties.redirectUrl" -o tsv \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/private-mcp-oauth?api-version=2025-06-01"
# => https://global.consent.azure-apim.net/redirect/<connector-guid>
```

**2. Register that exact value back on your OAuth app:**

- **Origin 1 (GitHub / third-party):** paste it into the OAuth app's **Authorization callback URL** field.
- **Origin 2 (Azure / Entra):** add it to the app registration's **web** redirect URIs — `az ad app update --id <ENTRA_APPLICATION_ID> --web-redirect-uris <redirectUrl>`.

> The `<connector-guid>` is **unique per connection** — read it back rather than guess.
---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service; `azd deploy` upserts it (auto-promoting). Create the OAuth2 connection first (section A, step 1), then reference it by **name** via `project_connection_id`.

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: mcp
        server_label: private_mcp
        project_connection_id: private-mcp-oauth   # connection name from section A
        require_approval: never
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

**Requirements & gotchas:**

- Set **`FOUNDRY_PROJECT_ENDPOINT` and `AZURE_SUBSCRIPTION_ID`** in the azd env before `azd deploy`, or it errors `infrastructure has not been provisioned`. No `azd provision` / `infra:` block needed.
- Authed MCP servers (static key, OAuth, agent identity, Entra passthrough) use `project_connection_id`; no-auth servers use inline `server_url`.
- The `-32006` consent gate still applies — the first `tools/list` triggers one-time consent (see [test-endpoint.md § OAuth consent flow](test-endpoint.md#oauth-consent-flow--32006)).

The agent references the toolbox **by name** (`TOOLBOX_NAME`); the endpoint resolves at runtime. See [use-toolbox-in-hosted-agent.md](../../create/references/use-toolbox-in-hosted-agent.md).

---

## Verify

Call `tools/list` against the endpoint — see [test-endpoint.md](test-endpoint.md). The first call for an un-consented user returns the `-32006` consent gate; see [test-endpoint.md § OAuth consent flow](test-endpoint.md#oauth-consent-flow--32006).

## References

- [Build and register an MCP server (custom MCP on Azure Functions)](https://learn.microsoft.com/en-us/azure/foundry/mcp/build-your-own-mcp-server?view=foundry)
- [MCP tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/mcp)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types) — all six MCP auth modes at a glance
