# Trace-to-Dataset Pipeline — Harvest Production Traces as Test Cases

Extract production traces from App Insights using KQL, transform them into evaluation dataset format, and persist as versioned datasets. This is the core workflow for turning real-world agent failures into reproducible test cases.

## ⛔ Do NOT

- Do NOT use `parse_json(customDimensions)` — `customDimensions` is already a `dynamic` column in App Insights KQL. Access properties directly: `customDimensions["gen_ai.response.id"]`.

## Related References

- [Eval Correlation](../../trace/references/eval-correlation.md) (in `foundry-agent/trace/references/`) — look up eval scores by response/conversation ID via `customEvents`
- [KQL Templates](../../trace/references/kql-templates.md) (in `foundry-agent/trace/references/`) — general trace query patterns and attribute mappings

## Prerequisites

- App Insights resource resolved (see [trace skill](../../trace/trace.md) Before Starting)
- Agent root, selected metadata file, environment, and project endpoint available from `.foundry/agent-metadata*.yaml`
- Time range confirmed with user (default: last 7 days)

When a repo contains multiple agent roots, this workflow updates only the selected agent root's `.foundry/datasets/`, `.foundry/results/`, and metadata files. Do **not** merge sibling agent folders.

> 💡 **Run all KQL queries** using **`monitor_resource_log_query`** (Azure MCP tool) against the App Insights resource. This is preferred over delegating to the `azure-kusto` skill.

> ⚠️ **Always pass `subscription` explicitly** to Azure MCP tools — they don't extract it from resource IDs.

## Overview

```
App Insights traces
    │
    ▼
[1] KQL Harvest Query (filter by error/latency/eval score)
    │
    ▼
[2] Schema Transform (trace → JSONL format)
    │
    ▼
[3] Human Review (show candidates, let user approve/edit/reject)
    │
    ▼
[4] Persist Dataset (local JSONL files)
    │
    ▼
[5] Sync to Foundry (optional — upload to project-connected storage)
```

## Key Concept: Linking Evaluation Results to Traces

> 💡 **Evaluation results live in `customEvents`, not in `dependencies`.** Foundry writes eval scores to App Insights as `customEvents` with `name == "gen_ai.evaluation.result"`. Agent traces (spans) live in `dependencies`. The link between them is **`gen_ai.response.id`** — this field appears on both tables.

| Table | Contains | Join Key |
|-------|----------|----------|
| `dependencies` | Agent traces (spans, tool calls, LLM calls) | `customDimensions["gen_ai.response.id"]` |
| `customEvents` | Evaluation results (scores, labels, explanations) | `customDimensions["gen_ai.response.id"]` |

**To harvest traces with eval scores**, join `customEvents` → `dependencies` on `responseId`. The [Low-Eval Harvest](#low-eval-harvest--traces-with-poor-evaluation-scores) template below shows this pattern. For standalone eval lookups, see [Eval Correlation](../../trace/references/eval-correlation.md) (in `foundry-agent/trace/references/`).

## Step 1 — Choose a Harvest Template

Select the appropriate KQL template based on user intent. These templates mirror common LangSmith "run rules" but offer more power through KQL's query language.

> ⚠️ **Hosted agents:** The Foundry agent name (e.g., `hosted-agent-022-001`) only appears on `requests`, NOT on `dependencies`. For hosted agents, use the [Hosted Agent Harvest](#hosted-agent-harvest) template which joins via `requests.id` → `dependencies.operation_ParentId`. The templates below work directly for **prompt agents** where `gen_ai.agent.name` on `dependencies` matches the Foundry name.

### Error Harvest — Failed Traces

Captures all traces where the agent returned errors. Equivalent to LangSmith's `eq(error, True)` run rule.

```kql
dependencies
| where timestamp > ago(7d)
| where success == false
| where isnotempty(customDimensions["gen_ai.operation.name"])
| where customDimensions["gen_ai.agent.name"] == "<agent-name>"
| extend
    conversationId = tostring(customDimensions["gen_ai.conversation.id"]),
    responseId = tostring(customDimensions["gen_ai.response.id"]),
    operation = tostring(customDimensions["gen_ai.operation.name"]),
    model = tostring(customDimensions["gen_ai.request.model"]),
    errorType = tostring(customDimensions["error.type"]),
    inputTokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
    outputTokens = toint(customDimensions["gen_ai.usage.output_tokens"])
| summarize
    errorCount = count(),
    errors = make_set(errorType, 5),
    firstSeen = min(timestamp),
    lastSeen = max(timestamp)
    by conversationId, responseId, operation, model
| order by lastSeen desc
| take 100
```

### Low-Eval Harvest — Traces with Poor Evaluation Scores

Captures traces where evaluator scores fell below a threshold. Equivalent to LangSmith's `and(eq(feedback_key, "quality"), lt(feedback_score, 0.3))` run rule.

```kql
let lowEvalResponses = customEvents
| where timestamp > ago(7d)
| where name == "gen_ai.evaluation.result"
| extend
    score = todouble(customDimensions["gen_ai.evaluation.score.value"]),
    evalName = tostring(customDimensions["gen_ai.evaluation.name"]),
    responseId = tostring(customDimensions["gen_ai.response.id"]),
    conversationId = tostring(customDimensions["gen_ai.conversation.id"])
| where score < <threshold>
| project responseId, conversationId, evalName, score;
lowEvalResponses
| join kind=inner (
    dependencies
    | where timestamp > ago(7d)
    | where isnotempty(customDimensions["gen_ai.response.id"])
    | extend responseId = tostring(customDimensions["gen_ai.response.id"])
) on responseId
| extend
    operation = tostring(customDimensions["gen_ai.operation.name"]),
    model = tostring(customDimensions["gen_ai.request.model"]),
    inputTokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
    outputTokens = toint(customDimensions["gen_ai.usage.output_tokens"])
| project timestamp, conversationId, responseId, evalName, score, operation, model, duration
| order by score asc
| take 100
```

> 💡 **Tip:** Replace `<threshold>` with the pass threshold from your evaluator config. Common values: `3.0` for 1–5 ordinal scales, `0.5` for 0–1 continuous scales.

### Latency Harvest — Slow Responses

Captures traces where response latency exceeds a threshold. Equivalent to LangSmith's `gt(latency, 5000)` run rule.

```kql
dependencies
| where timestamp > ago(7d)
| where duration > <threshold_ms>
| where isnotempty(customDimensions["gen_ai.operation.name"])
| where customDimensions["gen_ai.agent.name"] == "<agent-name>"
| extend
    conversationId = tostring(customDimensions["gen_ai.conversation.id"]),
    responseId = tostring(customDimensions["gen_ai.response.id"]),
    operation = tostring(customDimensions["gen_ai.operation.name"]),
    model = tostring(customDimensions["gen_ai.request.model"]),
    inputTokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
    outputTokens = toint(customDimensions["gen_ai.usage.output_tokens"])
| summarize
    avgDuration = avg(duration),
    maxDuration = max(duration),
    spanCount = count()
    by conversationId, responseId, operation, model
| order by maxDuration desc
| take 100
```

> 💡 **Tip:** Replace `<threshold_ms>` with the latency threshold in milliseconds. Common values: `5000` (5s), `10000` (10s), `30000` (30s).

### Combined Harvest — Multi-Criteria Filter

Combines multiple filters in a single query. Equivalent to LangSmith's compound rule: `and(gt(latency, 2000), eq(error, true), has(tags, "prod"))`.

```kql
dependencies
| where timestamp > ago(7d)
| where customDimensions["gen_ai.agent.name"] == "<agent-name>"
| where isnotempty(customDimensions["gen_ai.operation.name"])
| where success == false or duration > <threshold_ms>
| extend
    conversationId = tostring(customDimensions["gen_ai.conversation.id"]),
    responseId = tostring(customDimensions["gen_ai.response.id"]),
    operation = tostring(customDimensions["gen_ai.operation.name"]),
    model = tostring(customDimensions["gen_ai.request.model"]),
    errorType = tostring(customDimensions["error.type"]),
    inputTokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
    outputTokens = toint(customDimensions["gen_ai.usage.output_tokens"])
| summarize
    errorCount = countif(success == false),
    avgDuration = avg(duration),
    maxDuration = max(duration),
    spanCount = count()
    by conversationId, responseId, operation, model
| order by errorCount desc, maxDuration desc
| take 100
```

### Sampling — Control Dataset Size

Add `| sample <N>` or `| take <N>` to any harvest query to control the number of traces extracted. Equivalent to LangSmith's `sampling_rate` parameter.

```kql
// Random sample of 50 traces from the harvest
... | sample 50

// Top 50 most recent traces
... | order by timestamp desc | take 50

// Stratified sample: 20 errors + 20 slow + 10 low-eval
// Run each harvest separately and combine
```

### Hosted Agent Harvest — Two-Step Join Pattern

For hosted agents, the Foundry agent name lives on `requests`, not `dependencies`. Use this two-step pattern:

```kql
let reqIds = requests
| where timestamp > ago(7d)
| where customDimensions["gen_ai.agent.name"] == "<foundry-agent-name>"
| distinct id;
dependencies
| where timestamp > ago(7d)
| where operation_ParentId in (reqIds)
| where customDimensions["gen_ai.operation.name"] == "invoke_agent"
| extend
    conversationId = tostring(customDimensions["gen_ai.conversation.id"]),
    responseId = tostring(customDimensions["gen_ai.response.id"]),
    operation = tostring(customDimensions["gen_ai.operation.name"]),
    model = tostring(customDimensions["gen_ai.request.model"]),
    inputTokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
    outputTokens = toint(customDimensions["gen_ai.usage.output_tokens"])
| project timestamp, duration, success, conversationId, responseId, operation, model, inputTokens, outputTokens
| order by timestamp desc
| take 100
```

> 💡 **When to use this pattern:** If the direct `dependencies` filter by `gen_ai.agent.name` returns no results, the agent is likely a hosted agent where `gen_ai.agent.name` on `dependencies` holds the code-level class name (e.g., `BingSearchAgent`), not the Foundry name. Switch to this `requests` → `dependencies` join.

## Step 2 — Schema Transform

Transform harvested traces into JSONL dataset format. Each line in the JSONL file must contain:

| Field | Required | Source |
|-------|----------|--------|
| `query` | ✅ | User input — extract from `gen_ai.input.messages` on `invoke_agent` dependency spans |
| `response` | Optional | Agent output — extract from `gen_ai.output.messages` on `invoke_agent` dependency spans |
| `context` | Optional | Tool results or retrieved documents from the trace |
| `ground_truth` | Optional | Expected correct answer (add during curation) |
| `metadata` | Optional | Source info: `{"source": "trace", "conversationId": "...", "harvestRule": "error"}` |

### Extracting Input/Output from Traces

The full input/output content lives on `invoke_agent` dependency spans in `gen_ai.input.messages` and `gen_ai.output.messages`. These contain complete message arrays:

```json
// gen_ai.input.messages structure:
[{"role": "user", "parts": [{"type": "text", "content": "How do I reset my password?"}]}]

// gen_ai.output.messages structure:
[{"role": "assistant", "parts": [{"type": "text", "content": "To reset your password..."}]}]
```

Query to extract input/output for a specific conversation:

```kql
dependencies
| where customDimensions["gen_ai.conversation.id"] == "<conversation-id>"
| where customDimensions["gen_ai.operation.name"] in ("invoke_agent", "execute_agent", "chat", "create_response")
| extend
    responseId = tostring(customDimensions["gen_ai.response.id"]),
    operation = tostring(customDimensions["gen_ai.operation.name"]),
    inputMessages = tostring(customDimensions["gen_ai.input.messages"]),
    outputMessages = tostring(customDimensions["gen_ai.output.messages"])
| order by timestamp asc
| take 10
```

Extract the `query` from the last user-role entry in `gen_ai.input.messages` and the `response` from `gen_ai.output.messages`. Save extracted data to a local JSONL file:

```
.foundry/datasets/<agent-name>-traces-candidates-<date>.jsonl
```

## Step 3 — Human Review (Curation)

> ⚠️ **MANDATORY:** Never auto-commit harvested traces to a dataset. Always show candidates to the user first.

Present the harvested candidates as a table:

| # | Conversation ID | Error Type | Duration | Eval Score | Query (preview) |
|---|----------------|------------|----------|------------|----------------|
| 1 | conv-abc-123 | TimeoutError | 12.3s | 2.0 | "How do I reset my..." |
| 2 | conv-def-456 | None | 8.7s | 1.5 | "What's the status of..." |
| 3 | conv-ghi-789 | ValidationError | 0.4s | 3.0 | "Can you help me with..." |

Ask the user:
- *"Which candidates should I include in the dataset? (all / select by number / filter by criteria)"*
- *"Would you like to add ground_truth reference answers for any of these?"*
- *"What should I name this dataset version?"*

## Step 4 — Persist Dataset (Local JSONL)

Save approved candidates to `.foundry/datasets/<agent-name>-<source>-v<N>.jsonl`:

```json
{"query": "How do I reset my password?", "context": "User account management", "metadata": {"source": "trace", "conversationId": "conv-abc-123", "harvestRule": "error"}}
{"query": "What's the status of my order?", "response": "...", "ground_truth": "Order #12345 shipped on...", "metadata": {"source": "trace", "conversationId": "conv-def-456", "harvestRule": "latency"}}
```

### Update Manifest

After persisting, update `.foundry/datasets/manifest.json` with lineage information:

```json
{
  "datasets": [
    {
      "name": "support-bot-prod-traces",
      "file": "support-bot-prod-traces-v3.jsonl",
      "version": "v3",
      "source": "trace-harvest",
      "harvestRule": "error+latency",
      "timeRange": "2025-02-01 to 2025-02-07",
      "exampleCount": 47,
      "createdAt": "2025-02-08T10:00:00Z",
      "reviewedBy": "user"
    }
  ]
}
```

## Next Steps

After creating a dataset:
- **Sync to Foundry** → Step 5 below (recommended for shared/CI use)
- **Run evaluation** → [observe skill Step 2](../../observe/references/evaluate-step.md)
- **Version and tag** → [Dataset Versioning](dataset-versioning.md)
- **Organize into splits** → [Dataset Organization](dataset-organization.md)

## Step 5 — Sync Local Cache with Foundry (Optional)

Refresh or register the local cache in Foundry so it is available for server-side evaluations, shared access, and CI/CD pipelines. Reuse the local cache when it is current, and only refresh or push after user confirmation.

### 5a. Discover Storage Connection

Use `project_connection_list` to find an existing `AzureStorageAccount` connection on the Foundry project:

```
project_connection_list(foundryProjectResourceId, category: "AzureStorageAccount")
```

- **Found** → use its `connectionName` and `target` (storage account URL)
- **Not found** → proceed to 5b

### 5b. Create Storage Connection (if needed)

Ask the user for a storage account, then create a project connection:

```
project_connection_create(
  foundryProjectResourceId,
  connectionName: "datasets-storage",
  category: "AzureStorageAccount",
  target: "https://<storage-account>.blob.core.windows.net",
  authType: "AAD"
)
```

> 💡 **Tip:** The storage account must be in the same subscription or the user must have access. AAD auth is preferred — it uses the caller's identity.

### 5c. Upload JSONL to Blob Storage

Upload the local dataset file to the same `eval-datasets` container used for seed datasets so all Foundry-registered eval datasets follow one storage pattern:

```bash
az storage blob upload \
  --account-name <storage-account> \
  --container-name eval-datasets \
  --name <agent-name>/<agent-name>-<source>-v<N>.jsonl \
  --file .foundry/datasets/<agent-name>-<source>-v<N>.jsonl \
  --auth-mode login
```

The local dataset filename should start with the selected Foundry agent name before the source/stage/version suffixes so trace-derived datasets stay grouped with the owning agent.

> ⚠️ **Always pass `--auth-mode login`** to use AAD credentials. If the container doesn't exist, create it first with `az storage container create`.

### 5d. Register Dataset in Foundry

Use `evaluation_dataset_create` with the blob URI and the `AzureStorageAccount` `connectionName` discovered in 5a or created in 5b. While `connectionName` can be optional in other MCP flows, include it in this workflow so the dataset is bound to the project-connected storage account:

```
evaluation_dataset_create(
  projectEndpoint: "<project-endpoint>",
  datasetContentUri: "https://<storage-account>.blob.core.windows.net/eval-datasets/<agent-name>/<agent-name>-<source>-v<N>.jsonl",
  connectionName: "datasets-storage",
  datasetName: "<agent-name>-<source>",
  datasetVersion: "v<N>"
)
```

### 5e. Verify

Confirm the dataset is registered:

```
evaluation_dataset_get(projectEndpoint, datasetName: "<agent-name>-<source>", datasetVersion: "v<N>")
```

Display the registered dataset details to the user. Update `.foundry/datasets/manifest.json` with `"synced": true` and the server-side dataset name/version.
