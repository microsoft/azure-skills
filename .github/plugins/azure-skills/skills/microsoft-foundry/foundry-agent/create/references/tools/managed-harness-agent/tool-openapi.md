# OpenAPI

Expose an API through an inline OpenAPI 3.x document. Every callable operation needs an `operationId`.

Anonymous example:

```yaml
tools:
  - type: openapi
    openapi:
      name: weather
      description: Weather service
      spec:
        openapi: 3.0.0
        info: { title: Weather, version: 1.0.0 }
        servers: [{ url: https://api.example.com }]
        paths: {}
      auth:
        type: anonymous
```

Supported auth paths:

| Auth | Configuration | Connection |
|---|---|---|
| Anonymous | `type: anonymous` | No |
| Project connection | `type: connection`, `connection_id: <name-or-id>` | Yes |
| Managed identity | `type: managed_identity`, `audience: <resource-uri>` | No; grant project identity RBAC |

For API-key authentication, create a connection only when explicitly requested:

```bash
azd ai connection create <connection-name> \
  --kind custom-keys \
  --target "https://api.example.com" \
  --custom-key x-api-key="<api-key>" \
  --project-endpoint "<project-endpoint>"
```

The key name must match the OpenAPI security scheme. Keep secrets out of `azure.yaml`.

Multiple OpenAPI tools should use distinct `openapi.name` and `info.title` values.
