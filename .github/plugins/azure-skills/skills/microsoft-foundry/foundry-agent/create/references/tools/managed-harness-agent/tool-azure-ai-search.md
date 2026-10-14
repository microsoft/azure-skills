# Azure AI Search

Ground a Managed Harness Agent with an existing Azure AI Search index and Cognitive Search project connection.

```yaml
tools:
  - type: azure_ai_search
    azure_ai_search:
      indexes:
        - project_connection_id: <search-connection>
          index_name: <index-name>
          query_type: vector_semantic_hybrid
          top_k: 5
```

Use exactly one index reference mode per entry. The normal mode is `project_connection_id` plus `index_name`.

The user must supply the connection or the existing Agent must already reference it. If explicit creation is requested:

```bash
azd ai connection create <connection-name> \
  --kind cognitive-search \
  --target "https://<search-service>.search.windows.net/" \
  --auth-type api-key \
  --key "<search-key>" \
  --project-endpoint "<project-endpoint>"
```

Keep the key out of source control. For keyless access, ensure the Foundry project identity has the required Search data-plane roles.

The index must already exist and contain searchable/retrievable fields. Do not create or populate an index unless the user explicitly requests that separate work.

Foundry owns the nested tool contract; preserve a known-good current REST shape when extending fields such as filters or ranking options.
