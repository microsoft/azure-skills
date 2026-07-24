# Tool — Azure AI Search (`type: azure_ai_search`)

Attach an Azure AI Search index to a toolbox. The index is referenced by an existing **`CognitiveSearch`** project connection (connection kind `cognitive-search`). The tool uses the **nested** shape: an `azure_ai_search: { indexes: [...] }` object under the tool entry, where each index carries `project_connection_id` + `index_name` (not a top-level `connections:` array). For the toolbox concept, versions, and endpoint, see [toolbox.md](../toolbox.md).

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

---

## Prerequisites — search service and index

The toolbox tool references an existing index (behind a `CognitiveSearch` connection created in Section A). If you already have a populated index, skip to Section A. Otherwise set it up once:

### 1. Create a search service

```bash
RG=my-rg
SVC=my-search-svc        # must be globally unique
az search service create --name "$SVC" --resource-group "$RG" --sku Basic --location eastus
```

> If create fails with `InsufficientResourcesAvailable`, the region is out of capacity — try another region (`eastus`, `westus2`, `westus3`, …). The search service can live in a **different region** than your Foundry project; the connection targets it by URL.

Grab the endpoint + admin key for the next steps:

```bash
SURL="https://$SVC.search.windows.net"
KEY=$(az search admin-key show --service-name "$SVC" --resource-group "$RG" --query primaryKey -o tsv)
```

### 2. Create an index and upload local docs

Create an index with a key + searchable fields, then upload your documents (here, content pulled from local files):

```bash
# Create the index
curl -sS -X PUT "$SURL/indexes/contoso-outdoors?api-version=2023-11-01" \
  -H "api-key: $KEY" -H "Content-Type: application/json" \
  -d '{"name":"contoso-outdoors","fields":[
    {"name":"id","type":"Edm.String","key":true},
    {"name":"title","type":"Edm.String","searchable":true},
    {"name":"content","type":"Edm.String","searchable":true}]}'

# Upload documents (one object per file/record; @search.action=upload)
curl -sS -X POST "$SURL/indexes/contoso-outdoors/docs/index?api-version=2023-11-01" \
  -H "api-key: $KEY" -H "Content-Type: application/json" \
  -d '{"value":[
    {"@search.action":"upload","id":"1","title":"Zephyr Tent","content":"The Zephyr 2-person tent weighs 1.8kg and packs to 42cm."},
    {"@search.action":"upload","id":"2","title":"Aurora Sleeping Bag","content":"The Aurora bag is rated to -10C and uses 800-fill down."}]}'

# Confirm search returns your data (wait a few seconds for indexing)
curl -sS "$SURL/indexes/contoso-outdoors/docs?api-version=2023-11-01&search=tent" -H "api-key: $KEY"
```

> To load real files, read each file's text into the `content` field of an upload object (JSON), or use an Azure AI Search **indexer** over a Blob container for bulk/automatic ingestion.

---

# A. Imperative CLI

**Create the `CognitiveSearch` connection** — the tool references the index by this connection, which must exist first:

```bash
azd ai connection create my-search-conn \
  --kind cognitive-search \
  --target "$SURL/" \
  --auth-type api-key --key "$KEY"
```

Use the connection's name/id as `project_connection_id` below, and your index name as `index_name`.

Then create the toolbox — steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# Write the toolbox spec to a file
cat > ais.yaml <<'EOF'
description: azure ai search toolbox
tools:
  - type: azure_ai_search
    name: search
    azure_ai_search:
      indexes:
        - project_connection_id: my-search-conn   # the CognitiveSearch connection
          index_name: contoso-outdoors            # your index
          query_type: simple                       # simple | semantic | vector | vector_simple_hybrid | vector_semantic_hybrid
          top_k: 5
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file ais.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

For multiple indexes, add more entries to the `indexes:` list.

`--from-file` entry:

```yaml
tools:
  - type: azure_ai_search
    name: search
    azure_ai_search:
      indexes:
        - project_connection_id: my-search-conn
          index_name: contoso-outdoors
          query_type: simple
          top_k: 5
```

> **Index config is mutually exclusive** per entry: use exactly one of `project_connection_id` + `index_name` (V2), `index_connection_id` + `index_name` (V1), or `index_asset_id` alone (a registered index). Sending more than one fails service-side validation.

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service in `azure.yaml`; `azd deploy` upserts it (and auto-promotes the new version). Needs only an **existing** Foundry project (via `FOUNDRY_PROJECT_ENDPOINT` + `AZURE_SUBSCRIPTION_ID` in the azd env) — **no `azd provision`**, no `infra:` block. The `CognitiveSearch` connection must already exist (create it as shown in Section A).

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: azure_ai_search
        name: search
        azure_ai_search:
          indexes:
            - project_connection_id: my-search-conn
              index_name: contoso-outdoors
              query_type: simple
              top_k: 5

  # A hosted agent in the same project consumes the toolbox by name
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

---

## Verify & deploy

After creating the toolbox either way, verify its MCP endpoint end-to-end — see [test-endpoint.md](test-endpoint.md). The tool surfaces under the `name` you gave it (e.g. `search`) and `tools/call` takes a `query`:

```bash
TOK=$(az account get-access-token --resource "https://ai.azure.com" --query accessToken -o tsv)
URL="$FOUNDRY_PROJECT_ENDPOINT/toolboxes/agent-tools/mcp?api-version=v1"
curl -s -X POST "$URL" -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search","arguments":{"query":"your question"}}}'
```

Citations come back under `result.structuredContent.documents[]` (each doc = one citation with `title` / `id` / `score`; add a `url` field to your index to populate it) — see [use-toolbox-in-hosted-agent.md § Azure AI Search Citation Pattern](../../create/references/use-toolbox-in-hosted-agent.md#azure-ai-search-citation-pattern).

---

## References

- [Azure AI Search tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/azure-ai-search)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
