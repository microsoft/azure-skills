# Step 1 — Auto-Setup Evaluators & Dataset

> **This step runs automatically after deployment.** If the agent was deployed via the [deploy skill](../../deploy/deploy.md), `.foundry` cache and metadata may already be configured. Check `.foundry/evaluators/`, `.foundry/datasets/`, and the selected metadata file under the selected agent root before re-creating them.
>
> If the agent is **not yet deployed**, follow the [deploy skill](../../deploy/deploy.md) first. It handles project detection, Dockerfile generation, ACR build, agent creation, verification, and auto-creates `.foundry` cache after a successful deployment.

## Auto-Create Evaluators & Dataset

> **This step is fully automatic.** After deployment, immediately prepare evaluators and a local test dataset for the selected environment without waiting for the user to request it.

### 1. Read Agent Instructions

Use **`agent_get`** (or local `agent.yaml` in the selected agent root) to understand the agent's purpose and capabilities.

### 2. Reuse or Refresh Cache

Inspect `.foundry/evaluators/`, `.foundry/datasets/`, and the selected environment's `evaluationSuites[]` in the selected agent root only. Do **not** merge sibling agent folders. If the selected environment still uses older `testSuites[]` or legacy `testCases[]`, normalize that list to evaluation suites first and plan to rewrite that environment as `evaluationSuites[]` when this step persists metadata.

- **Cache is current** -> reuse it and summarize what is already available.
- **Cache is missing or stale** -> refresh it after confirming with the user.
- **User explicitly asks for refresh** -> rebuild and rewrite only the selected environment's cache in the selected agent root.

### 2.5 Discover Existing Evaluators

Use **`evaluator_catalog_get`** with the selected environment's project endpoint to list all evaluators already registered in the project. Display them to the user grouped by type (`custom` vs `built-in`) with name, category, and version. During Phase 1, catalog any promising custom evaluators for later reuse, but keep the first run on the built-in baseline. Only propose creating a new evaluator in Phase 2 when no existing evaluator covers a required dimension.

### 3. Select Evaluators

Follow the [Two-Phase Evaluator Strategy](../observe.md). Phase 1 is built-in only, so do not create a new custom evaluator during the initial setup pass.

Start with <=5 built-in evaluators for the initial eval run so the first pass stays fast:

| Category | Evaluators |
|----------|-----------|
| **Quality (built-in)** | relevance, task_adherence, intent_resolution |
| **Safety (built-in)** | indirect_attack |
| **Tool use (built-in, conditional)** | tool_call_accuracy (use when the agent calls tools; some catalogs label it as `builtin.tool_call_accuracy`) |

After analyzing initial results, suggest additional evaluators (custom or built-in) targeted at specific failure patterns instead of front-loading a broad default set.

### 4. Defer New Custom Evaluators to Phase 2

During the initial setup pass, do not create a new custom evaluator yet. Instead, record which existing custom evaluators from Step 2.5 might be reused later and run the first built-in-only eval. After the first run has been analyzed, return to this step only if the built-in judges still miss an important pattern.

When Phase 2 is needed:

1. Call **`evaluator_catalog_get`** again and reuse an existing custom evaluator if it already covers the gap.
2. Only if the catalog still lacks the required signal, use **`evaluator_catalog_create`** with the selected environment's project endpoint.
3. Prefer evaluators that consume `expected_behavior`, as described in the [Two-Phase Evaluator Strategy](../observe.md), so scoring can follow the per-query rubric instead of only the global agent instructions.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `projectEndpoint` | ✅ | Azure AI Project endpoint |
| `name` | ✅ | For example, `domain_accuracy`, `citation_quality` |
| `category` | ✅ | `quality`, `safety`, or `agents` |
| `scoringType` | ✅ | `ordinal`, `continuous`, or `boolean` |
| `promptText` | ✅* | Template with `{{query}}`, `{{response}}`, and `{{expected_behavior}}` placeholders when behavior-specific scoring is needed |
| `minScore` / `maxScore` | | Default: 1 / 5 |
| `passThreshold` | | Scores >= this value pass |

### 5. Identify LLM-Judge Deployment

Use **`model_deployment_get`** to list the selected project's actual model deployments, then choose one that supports chat completions for quality evaluators. Do **not** assume `gpt-4o` exists in the project. If no deployment supports chat completions, stop the setup flow and explain that quality evaluators need a compatible judge deployment.

### 6. Generate Local Test Dataset

Generate the seed rows directly from the selected agent root's instructions and tool capabilities you already resolved during setup. Do **not** call the identified chat-capable deployment for dataset generation; reserve that deployment for quality evaluators. Save the initial seed file to `.foundry/datasets/<agent-name>-eval-seed-v1.jsonl` with each line containing at minimum `query` and `expected_behavior` fields (optionally `context`, `ground_truth`).

The local filename must start with the selected environment's Foundry agent name (`agentName` in the selected metadata file) before adding stage, environment, or version suffixes.

Include `expected_behavior` even though Phase 1 uses built-in evaluators only. That field pre-positions the seed dataset for Phase 2 custom evaluators if the first run reveals gaps that need a per-query behavioral rubric.

Use [Generate Seed Evaluation Dataset](../../eval-datasets/references/generate-seed-dataset.md) as the single source of truth for registration. It covers `project_connection_list` with `AzureStorageAccount`, key-based versus AAD upload, `evaluation_dataset_create` with `connectionName`, and saving the returned `datasetUri`.

### 7. Persist Artifacts and Evaluation Suites

```text
.foundry/
  agent-metadata.yaml
  agent-metadata.prod.yaml
  evaluators/
    <name>.yaml
  datasets/
    *.jsonl
  results/
    <environment>/
      <eval-id>/
        <run-id>.json
```

Save evaluator definitions to `.foundry/evaluators/<name>.yaml`, test data to `.foundry/datasets/*.jsonl`, and create or update evaluation suites in the selected metadata file with:
- `id`
- `tags` (freeform key/value map, for example `tier: smoke`, `purpose: baseline`, `stage: seed`)
- `dataset` (for example, `<agent-name>-eval-seed`)
- `datasetVersion` (for example, `v1`)
- `datasetFile` (for example, `.foundry/datasets/<agent-name>-eval-seed-v1.jsonl`)
- `datasetUri` (returned by `evaluation_dataset_create`)
- tag values for `agent`, `stage`, and `version`
- evaluator names and thresholds

If the selected environment still uses older `testSuites[]` or legacy `testCases[]`, replace that list with `evaluationSuites[]` in the rewritten metadata. Preserve dataset/evaluator fields and map `priority` to `tags.tier` only when `tags.tier` is missing.

> ⚠️ **Show Data Viewer deeplinks (for VS Code runtime only):** Append a Data Viewer deeplink immediately after reference to a dataset file in your response. Format: "[Open in Data Viewer](vscode://ms-windows-ai-studio.windows-ai-studio/open_data_viewer?file=<file_path>&source=microsoft-foundry-skill) for details and perform analysis".

### 8. Prompt User

*"Your agent is deployed and running in the selected environment. The `.foundry` cache now contains evaluators, a local seed dataset, the Foundry dataset registration metadata, and evaluation-suite metadata. Would you like to run an evaluation to identify optimization opportunities?"*

If yes -> proceed to [Step 2: Evaluate](evaluate-step.md). If no -> stop.
