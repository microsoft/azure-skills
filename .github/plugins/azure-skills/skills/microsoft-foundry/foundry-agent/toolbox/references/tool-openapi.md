# Tool — OpenAPI (`type: openapi`)

Expose a REST API to the agent from its **OpenAPI 3.x spec**. The spec is embedded **inline** in the toolbox `tools:` block (under an `openapi` object) — this is a connectionless built-in, **not** a connection-backed tool. API-key auth is the one mode that also needs a `custom-keys` connection. For the toolbox concept, versions, and endpoint, see [toolbox.md](../toolbox.md).

Each operation becomes one tool named `{name}___{operationId}`, so every operation in the spec needs an `operationId` (letters, `-`, `_` only).

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

## Tool entry shape

```yaml
tools:
  - type: openapi
    openapi:
      name: catfacts            # tool-name prefix: {name}___{operationId}
      spec: { <inline OpenAPI 3.x document> }
      auth: { type: anonymous } # or connection / managed_identity — see below
```

## Auth modes

| Auth | `auth` object | Connection needed? |
|---|---|---|
| Anonymous | `{ type: anonymous }` | No |
| API key | `{ type: connection, connection_id: <custom-keys-connection-name> }` | Yes — a `custom-keys` connection whose key name matches the spec's `securityScheme` name |
| Managed identity | `{ type: managed_identity, audience: <resource-uri> }` | No — grant the project MI RBAC on the target, or calls return `401` |

---

# A. Imperative CLI (anonymous)

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# 1. (API-key auth only) create the custom-keys connection; the key name must match the spec's securityScheme name
azd ai connection create my-api-conn \
  --kind custom-keys --target https://api.example.com \
  --custom-key x-api-key="<api-key>" \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"

# Write the toolbox spec to a file (anonymous example)
cat > openapi.yaml <<'EOF'
description: openapi toolbox
tools:
  - type: openapi
    openapi:
      name: catfacts
      spec:
        openapi: "3.0.0"
        info: { title: Cat Facts, version: "1.0.0" }
        servers: [{ url: https://catfact.ninja }]
        paths:
          /fact:
            get:
              operationId: getFact
              responses: { "200": { description: ok } }
      auth:
        type: anonymous
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file openapi.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> **Add to an existing toolbox:** an `openapi` tool lives in the `tools:` block, and the `azd` CLI has **no `tool add`** command — only `connection add`. So you can only create a new toolbox (`azd ai toolbox create`) with the full tool set, not append an openapi tool to an existing one.

For **API-key** auth, swap the `auth` block and add `security` + `securitySchemes` to the spec:

```yaml
tools:
  - type: openapi
    openapi:
      name: my_api
      spec:
        openapi: "3.0.0"
        info: { title: My API, version: "1.0.0" }
        servers: [{ url: https://api.example.com }]
        security: [{ apiKeyHeader: [] }]
        components:
          securitySchemes:
            apiKeyHeader: { type: apiKey, name: x-api-key, in: header }   # name must match the connection key
        paths:
          /thing:
            get: { operationId: getThing, responses: { "200": { description: ok } } }
      auth:
        type: connection
        connection_id: my-api-conn
```

For **managed identity**, use `auth: { type: managed_identity, audience: https://<resource-uri>/ }` and grant the project MI the required RBAC role on the target.

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service; `azd deploy` upserts it (and auto-promotes the new version). The `openapi` tool goes under `tools:` exactly as in section A.

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: openapi
        openapi:
          name: catfacts
          spec:
            openapi: "3.0.0"
            info: { title: Cat Facts, version: "1.0.0" }
            servers: [{ url: https://catfact.ninja }]
            paths:
              /fact:
                get:
                  operationId: getFact
                  responses: { "200": { description: ok } }
          auth:
            type: anonymous
```

```bash
azd deploy agent-tools
```

Set **`FOUNDRY_PROJECT_ENDPOINT` and `AZURE_SUBSCRIPTION_ID`** in the azd env (after it's created) before `azd deploy`, or it errors `infrastructure has not been provisioned`. No `azd provision` / `infra:` block is needed. See [use-toolbox-in-hosted-agent.md](../../create/references/use-toolbox-in-hosted-agent.md) for wiring a hosted agent to the toolbox.

---

## Verify & deploy against Cat Facts

After creating the toolbox either way, verify its MCP endpoint end-to-end (bearer token + raw `tools/list` / `tools/call`) — see [test-endpoint.md](test-endpoint.md).

With the anonymous Cat Facts spec above: `tools/list` returns `catfacts___getFact`; `tools/call` on it returns a live cat fact (`{"fact": "...", "length": ...}`).

```bash
ENDPOINT=$(azd ai toolbox show agent-tools --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT" --output json \
  | python -c "import sys,json; print(json.load(sys.stdin)['endpoint'])")
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

curl -sS -X POST "$ENDPOINT" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"catfacts___getFact","arguments":{}}}' | python -m json.tool
```

> Multiple `openapi` entries are allowed in one toolbox only if each spec defines a distinct `info.title`. See [toolbox-azd.md § Multi-tool rule](toolbox-azd.md#multi-tool-rule).

## References

- [OpenAPI tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/openapi)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
