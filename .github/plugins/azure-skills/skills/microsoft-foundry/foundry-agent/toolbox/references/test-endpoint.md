# Testing the toolbox

After creating or updating a toolbox (steps 1–3 in each tool's setup guide), verify it works. Two ways: call the MCP endpoint directly, or exercise it through the deployed agent.

## 1. Call the toolbox endpoint directly

Verify the toolbox MCP endpoint end-to-end without an agent. Use `az login` for authentication, then test the MCP operations in order. For endpoint URL format and auth scope, see [toolbox.md § MCP endpoint URL format](../toolbox.md#mcp-endpoint-url-format).

**a. Get a bearer token:**

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
TOOLBOX_URL="https://<account>.services.ai.azure.com/api/projects/<project>/toolboxes/<name>/mcp?api-version=v1"
```

**b. (Optional) Initialize MCP session:**

The toolbox endpoint is stateless, so this step is not required — `tools/list` and `tools/call` work without it. Run it only to confirm the handshake:

```bash
curl -sS -X POST "$TOOLBOX_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"debug","version":"1.0.0"}}}' \
  -D - | head -20
```

No `mcp-session-id` header is returned, and none is needed on later calls.

**c. List tools:**

```bash
curl -sS -X POST "$TOOLBOX_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python -m json.tool
```

**d. Call a tool.** The argument shape is per-tool — read each tool's `inputSchema` from `tools/list`. Examples for the connectionless built-ins:

```bash
# web_search — arg is `search_query` (returns live Bing results)
curl -sS -X POST "$TOOLBOX_URL" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"<web_search_tool_name>","arguments":{"search_query":"latest Azure Foundry news"}}}' | python -m json.tool

# code_interpreter — arg is `code` (spins up a sandbox container and runs it; isError=false)
curl -sS -X POST "$TOOLBOX_URL" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"<code_interpreter_tool_name>","arguments":{"code":"print(6*7)"}}}' | python -m json.tool
```

> ⚠️ **Agent-identity-authed tools won't work locally — that's expected, not a blocker.** The token above is your **user** identity, not the deployed agent's. Use section 2 to test those.

## 2. Test it through the agent

Wire the toolbox endpoint into the agent, deploy, and invoke it — this exercises the tool with the deployed agent's identity (the only way to test agent-identity-authed tools):

```bash
# 1. Read the endpoint and set the env var
azd env set TOOLBOX_ENDPOINT "$(azd ai toolbox show <toolbox-name> --output json | python -c "import sys,json; print(json.load(sys.stdin)['endpoint'])")"

# 2. Reference TOOLBOX_ENDPOINT in the agent service's environmentVariables in azure.yaml, then deploy
azd deploy

# 3. Invoke the agent to confirm it sees and can call the tool
azd ai agent invoke "list the tools you have access to"
```

## OAuth consent flow (`-32006`)

For an **OAuth2** MCP connection (BYO custom app or Foundry-managed connector) whose caller has **not consented yet**, the first `tools/list` returns a consent gate instead of the tool list:

```jsonc
{"jsonrpc":"2.0","id":2,"error":{"code":-32006,
 "message":"tools/list failed for 1 tool source(s)... {\"errors\":[{\"name\":\"<server_label>\",\"type\":\"mcp\",
   \"error\":{\"code\":\"CONSENT_REQUIRED\",
     \"message\":\"https://logic-apis-<region>.consent.azure-apim.net/login?data=...\"}}]}"}}
```

- The nested `message` is the **consent URL** (host `logic-apis-<region>.consent.azure-apim.net` — the Foundry connector consent endpoint, **not** a raw `login.microsoftonline.com` URL). Open it in a browser and sign in to grant the connection.
- After consent, the toolbox caches the token; the same `tools/list` then returns the MCP's tools, and `tools/call` works.
- This `-32006` gate is the **expected** pre-consent behavior for OAuth2 — not an error to debug. **Consent is per-user, per-connection, per-project**; each new caller hits it once.
- BYO custom-app connections also require the connection's reply URL to be registered on your OAuth app first — see [tool-mcp-custom-oauth.md § Set the connector redirect URI](tool-mcp-custom-oauth.md#set-the-connector-redirect-uri-after-the-connection-exists).

### Consent / OAuth troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `tools/list` → `-32006 CONSENT_REQUIRED` | Expected on first use. Open the returned consent URL and sign in; retry. |
| `tools/list` → `-32007 HTTP_403` after consenting | Consent succeeded, but the MCP server rejected the token — its Easy Auth doesn't advertise the scope. For a self-built Functions MCP, set `WEBSITE_AUTH_PRM_DEFAULT_WITH_SCOPES=<ENTRA_IDENTIFIER_URI>/user_impersonation` on the Function App (see [tool-mcp-custom-oauth-azure-starter.md](tool-mcp-custom-oauth-azure-starter.md)). |
| `tools/list` → `-32007 HTTP_404` | Auth passed but the server has no tools at `/runtime/webhooks/mcp` — the MCP code isn't deployed. Publish a sample with `func azure functionapp publish <app>`. |
| `AADSTS...redirect_uri` mismatch after clicking consent | The connection's reply URL isn't registered on your app. Read `properties.redirectUrl` from the connection and add it to the app's redirect URIs — see [tool-mcp-custom-oauth.md § Set the connector redirect URI](tool-mcp-custom-oauth.md#set-the-connector-redirect-uri-after-the-connection-exists). |
| `invalid_client` at the token step | Wrong `--client-secret` (expired/mistyped) or `--client-id`. Reset the secret and recreate the connection. |
| `tools/list` returns zero after consent | Scope mismatch — `--scopes` must match the MCP's `scopes_supported` from `/.well-known/oauth-protected-resource`. |
| `tools/call` → `403 ... user may not be registered` | Managed connector backed by a dogfood OAuth app with a test-user allowlist — not fixable client-side. See [foundry-tool-catalog.md dogfood trap](../../create/references/foundry-tool-catalog.md#dogfood-oauth-app-runtime-allowlist-trap). |

## References

- [toolbox.md § MCP endpoint URL format](../toolbox.md#mcp-endpoint-url-format)
- [toolbox.md § The flow](../toolbox.md#the-flow) — the create→deploy steps
