# Tool — File Search (`type: file_search`)

Vector-store-backed retrieval over uploaded files — a **connectionless built-in** (the vector store is referenced by the toolbox tool). Use the **flat** tool shape: `vector_store_ids` is a sibling of `type`, not nested under `file_search`. For the toolbox concept, versions, and endpoint, see [toolbox.md](../toolbox.md).

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

---

## Prerequisite — create a vector store

File search needs a **vector store** populated with your files. Create it via the project's **OpenAI-compatible** endpoints (`{project}/openai/v1/...`), using a token scoped to `https://ai.azure.com/.default`. Requires **Storage Blob Data Contributor** on the project storage and **Foundry User/Owner** on the project.

```bash
PROJ="$FOUNDRY_PROJECT_ENDPOINT"
TOKEN=$(az account get-access-token --scope "https://ai.azure.com/.default" --query accessToken -o tsv)

# 1. Upload a file (purpose=assistants)
FILE_ID=$(curl -sS -X POST "$PROJ/openai/v1/files" -H "Authorization: Bearer $TOKEN" \
  -F purpose="assistants" -F file="@./mydoc.txt" | jq -r .id)

# 2. Create a vector store with that file
VS_ID=$(curl -sS -X POST "$PROJ/openai/v1/vector_stores" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "{\"name\":\"my-vs\",\"file_ids\":[\"$FILE_ID\"]}" | jq -r .id)

# 3. Poll until ingestion completes (status must be 'completed' before use)
curl -sS "$PROJ/openai/v1/vector_stores/$VS_ID" -H "Authorization: Bearer $TOKEN" | jq '.status, .file_counts'
```

Use the resulting `VS_ID` (form `vs_...`) below. One vector store per agent; up to 10,000 files per store; 512 MB per file.

---

# A. Imperative CLI

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow) — connectionless, so it goes under a `tools:` block. Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# Write the toolbox spec to a file (use the real VS_ID from the prerequisite)
cat > fs.yaml <<EOF
description: file-search toolbox
tools:
  - type: file_search
    vector_store_ids: ["$VS_ID"]   # flat: sibling of type, NOT nested under file_search
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file fs.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> **Add to an existing toolbox:** the current `azd` CLI does **not** support adding a connectionless built-in to an existing toolbox — you can only create a new toolbox (`azd ai toolbox create`) with the full tool set.

`--from-file` entry:

```yaml
tools:
  - type: file_search
    vector_store_ids: ["vs_..."]
```

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service in `azure.yaml`; `azd deploy` upserts it (and auto-promotes the new version). Needs only an **existing** Foundry project (via `FOUNDRY_PROJECT_ENDPOINT` + `AZURE_SUBSCRIPTION_ID` in the azd env) — **no `azd provision`**, no `infra:` block.

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: file_search
        vector_store_ids: ["vs_..."]   # flat shape

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

After creating the toolbox either way, verify its MCP endpoint end-to-end — see [test-endpoint.md](test-endpoint.md).

---

## References

- [File Search tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/file-search) — vector store creation, SDK/REST samples
- [Vector stores for file search](https://learn.microsoft.com/azure/foundry/agents/concepts/vector-stores)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
