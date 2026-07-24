# BYO OAuth2 — Azure-hosted MCP starter (build your own MCP on Functions)

Companion to [tool-mcp-custom-oauth.md](tool-mcp-custom-oauth.md). Use this when you want to **build** the MCP server yourself on Azure Functions (rather than register an OAuth app against a third-party MCP). Deploying the sample template creates the Function App **and** its Entra app registration, so four of the five BYO OAuth2 connection inputs come straight from its outputs — you only add a client secret.

Run the steps in order. They set env vars (`FUNC`, `RG`, `APPID`, `IDURI`, `TENANT`) that later steps reuse. Then return to [tool-mcp-custom-oauth.md § A. Imperative CLI](tool-mcp-custom-oauth.md#a-imperative-cli) with the inputs.

**Step 1 — Scaffold and provision the Function App + Entra app.**

```bash
azd init --template remote-mcp-functions-python -e mcpserver-python
azd env set AZURE_SUBSCRIPTION_ID <sub-id>
azd env set AZURE_LOCATION <region>       # e.g. eastus2
azd env set VNET_ENABLED false            # public endpoint (simplest); true for private networking
azd up --no-prompt
```

**Step 2 — Capture the outputs into shell vars** (used by every step below):

```bash
FUNC=$(azd env get-values  | grep AZURE_FUNCTION_NAME   | cut -d'"' -f2)
APPID=$(azd env get-values | grep ENTRA_APPLICATION_ID  | cut -d'"' -f2)
IDURI=$(azd env get-values | grep ENTRA_IDENTIFIER_URI  | cut -d'"' -f2)
TENANT=$(azd env get-values | grep AZURE_TENANT_ID      | cut -d'"' -f2)
RG="rg-$(azd env get-values | grep AZURE_ENV_NAME       | cut -d'"' -f2)"   # template puts resources in rg-<env-name>
```

**Step 3 — Deploy the MCP tool code.** `azd up` provisions infra only — the sample repo's `azure.yaml` has no `services:` mapping, so the Function App starts **empty** and `tools/list` would return `HTTP_404`. Publish one of the sample projects:

```bash
(cd src/FunctionsMcpTool && func azure functionapp publish "$FUNC")   # one of 4 sample projects
```

**Step 4 — Let the MCP's Easy Auth advertise its scope.** Without this the connector's token is rejected with `HTTP_403` even after consent:

```bash
az functionapp config appsettings set --name "$FUNC" --resource-group "$RG" \
  --settings "WEBSITE_AUTH_PRM_DEFAULT_WITH_SCOPES=$IDURI/user_impersonation"
```

The template already sets the Function App's `allowedAudiences` to `$IDURI` and `allowedApplications` to `$APPID` — the same `client-id` the connection uses — so the token validates.

**Step 5 — (optional) Confirm the scope** the server advertises matches what you'll pass as `--scopes`:

```bash
curl -s "https://$FUNC.azurewebsites.net/.well-known/oauth-protected-resource"
# => {"resource":"...","scopes_supported":["api://<identifier-uri>/user_impersonation"]}
```

**Step 6 — Create a client secret** on the Entra app (it lives on the connection, not the toolbox):

```bash
SECRET=$(az ad app credential reset --id "$APPID" --display-name toolbox-oauth2 --years 1 --query password -o tsv)
#   ⚠️ the command prints a WARNING line before the secret — take the LAST line if capturing text.
```

You now have all five connection inputs:

| Connection input | Value |
|---|---|
| `--client-id` | `$APPID` |
| `--client-secret` | `$SECRET` |
| `--authorization-url` | `https://login.microsoftonline.com/$TENANT/oauth2/v2.0/authorize` |
| `--token-url` | `https://login.microsoftonline.com/$TENANT/oauth2/v2.0/token` |
| `--scopes` | `$IDURI/user_impersonation` |

The connection **target** is `https://$FUNC.azurewebsites.net/runtime/webhooks/mcp`. Next: create the connection ([tool-mcp-custom-oauth.md § A](tool-mcp-custom-oauth.md#a-imperative-cli)), then [Set the connector redirect URI](tool-mcp-custom-oauth.md#set-the-connector-redirect-uri-after-the-connection-exists). Tear down with `azd down --purge` (and `az ad app delete --id "$APPID"`) when done.

## References

- [Build and register an MCP server (custom MCP on Azure Functions)](https://learn.microsoft.com/en-us/azure/foundry/mcp/build-your-own-mcp-server?view=foundry)
- [tool-mcp-custom-oauth.md](tool-mcp-custom-oauth.md) — the BYO OAuth2 connection + toolbox flow
