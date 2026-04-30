# Agent Metadata Contract

Use this contract for every agent source folder that participates in Microsoft Foundry workflows.

## Required Local Layout

```text
<agent-root>/
  .foundry/
    agent-metadata.yaml
    agent-metadata.prod.yaml
    datasets/
    evaluators/
    results/
```

- `agent-metadata.yaml` is the preferred local/dev metadata file.
- Optional sidecar files such as `agent-metadata.prod.yaml` can hold a single prod or CI-targeted environment without mixing multiple environments in one file.
- `datasets/` and `evaluators/` are local cache folders. Reuse existing files when they are current, and ask before refreshing or overwriting them.
- `results/` stores local evaluation outputs and comparison artifacts by environment.

## Metadata File Model

| File | Typical use | Notes |
|------|-------------|-------|
| `.foundry/agent-metadata.yaml` | Preferred local/dev metadata | Default choice for local workflows when no file is specified |
| `.foundry/agent-metadata.<env>.yaml` | Optional prod/CI or modular environment-specific metadata | Prefer this when the workflow explicitly targets that environment and the file exists |

New setups should prefer **one environment per metadata file** while keeping the current schema shape (`defaultEnvironment` + `environments.<name>`) for compatibility. Legacy multi-environment `agent-metadata.yaml` files remain supported.

## Environment Model

| Field | Required | Purpose |
|-------|----------|---------|
| `defaultEnvironment` | ✅ | Default environment inside the selected metadata file; in preferred single-environment files it should match the only environment key |
| `environments.<name>.projectEndpoint` | ✅ | Foundry project endpoint for that environment |
| `environments.<name>.agentName` | ✅ | Deployed Foundry agent name |
| `environments.<name>.azureContainerRegistry` | ✅ for hosted agents | ACR used for deployment and image refresh |
| `environments.<name>.observability.applicationInsightsResourceId` | Recommended | App Insights resource for trace workflows |
| `environments.<name>.observability.applicationInsightsConnectionString` | Optional | Connection string when needed for tooling |
| `environments.<name>.evaluationSuites[]` | ✅ | Dataset + local/remote references + evaluator + tag bundles for evaluation workflows |

## Example `.foundry/agent-metadata.yaml` (local/dev)

```yaml
defaultEnvironment: dev
environments:
  dev:
    projectEndpoint: https://contoso.services.ai.azure.com/api/projects/support-dev
    agentName: support-agent-dev
    azureContainerRegistry: contosoregistry.azurecr.io
    observability:
      applicationInsightsResourceId: /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Insights/components/support-dev-ai
    evaluationSuites:
      - id: smoke-core
        tags:
          tier: smoke
          purpose: baseline
          stage: seed
        dataset: support-agent-dev-eval-seed
        datasetVersion: v1
        datasetFile: .foundry/datasets/support-agent-dev-eval-seed-v1.jsonl
        datasetUri: <foundry-dataset-uri>
        evaluators:
          - name: intent_resolution
            threshold: 4
          - name: task_adherence
            threshold: 4
          - name: citation_quality
            threshold: 0.9
            definitionFile: .foundry/evaluators/citation-quality.yaml
      - id: trace-regression-suite
        tags:
          tier: regression
          purpose: regression
          stage: traces
        dataset: support-agent-dev-traces
        datasetVersion: v3
        datasetFile: .foundry/datasets/support-agent-dev-traces-v3.jsonl
        datasetUri: <foundry-dataset-uri>
        evaluators:
          - name: coherence
            threshold: 4
          - name: groundedness
            threshold: 4
```

## Example `.foundry/agent-metadata.prod.yaml` (prod/CI)

```yaml
defaultEnvironment: prod
environments:
  prod:
    projectEndpoint: https://contoso.services.ai.azure.com/api/projects/support-prod
    agentName: support-agent-prod
    azureContainerRegistry: contosoregistry.azurecr.io
    evaluationSuites:
      - id: production-guardrails
        tags:
          tier: smoke
          purpose: safety
          stage: prod
        dataset: support-agent-prod-curated
        datasetVersion: v2
        datasetFile: .foundry/datasets/support-agent-prod-curated-v2.jsonl
        datasetUri: <foundry-dataset-uri>
        evaluators:
          - name: violence
            threshold: 1
          - name: self_harm
            threshold: 1
```

## Workflow Rules

1. Auto-discover agent roots by searching for `.foundry/` folders that contain `agent-metadata.yaml` or `agent-metadata.<env>.yaml`.
2. If exactly one agent root is found, use it. If multiple roots are found, require the user to choose one.
3. Inside the selected agent root, select the metadata file in this order: explicit file/path from the user or workflow, then `.foundry/agent-metadata.<env>.yaml` when an explicit environment is already known and that file exists, then `.foundry/agent-metadata.yaml`. If `.foundry/agent-metadata.yaml` is absent, use the only matching sidecar file when exactly one `.foundry/agent-metadata.<env>.yaml` file exists; if multiple sidecar files exist and no explicit file/path was provided, require the user to choose the metadata file.
4. Resolve environment in this order: explicit user choice, then the file's only environment when the selected metadata file is single-environment, then remembered session choice, then `defaultEnvironment`.
5. Keep the selected agent root, metadata file, and environment visible in every deploy, eval, dataset, and trace summary.
6. Once an agent root is selected, use only that root's `.foundry/` folders and source tree for local evaluation, dataset, trace, deploy, and prompt-optimization context. Do not merge sibling agent folders.
7. Treat `datasets/` and `evaluators/` as cache folders. Reuse local files when present, but offer refresh when the user asks or when remote state is newer.
8. Writes must target the selected metadata file only. For preferred single-environment files, update only that one environment block. For legacy multi-environment files, rewrite only the selected environment block. Never copy or merge environments across sibling metadata files automatically.
9. Never overwrite cache files or metadata silently.

## Legacy Compatibility (`testCases[]` / `testSuites[]` -> `evaluationSuites[]`)

Use `evaluationSuites[]` as the canonical schema. If the selected environment still uses older `testSuites[]` and does not yet define `evaluationSuites[]`, treat that list as the current suite source, normalize it in memory, and migrate it on the next metadata write. If the selected environment is older still and uses legacy `testCases[]` without `evaluationSuites[]`, treat `testCases[]` as the suite source and normalize it the same way.

| Legacy field | Migration behavior |
|--------------|--------------------|
| `id` | Keep as-is |
| `dataset`, `datasetVersion`, `datasetFile`, `datasetUri`, `evaluators` | Keep as-is |
| `tags` | Preserve if already present |
| `priority` | If `tags.tier` is missing, map `P0` -> `smoke`, `P1` -> `regression`, `P2` -> `coverage` |

When a workflow writes metadata, rewrite the selected metadata file so the target environment contains only `evaluationSuites[]`. Do not keep older `testSuites[]` or legacy `testCases[]` in the rewritten block.

## Evaluation-Suite Guidance

Use `tags` as a freeform key/value map on each evaluation suite. Suggested keys:

| Tag Key | Example Values | Typical Use |
|---------|----------------|-------------|
| `tier` | `smoke`, `regression`, `coverage` | Suggested run order / breadth |
| `purpose` | `baseline`, `safety`, `tools`, `quality`, `regression` | Why the suite exists |
| `stage` | `seed`, `traces`, `curated`, `prod` | Dataset lifecycle alignment |

Each evaluation suite should point to one dataset and one or more evaluators with explicit thresholds. Store `dataset` as the stable Foundry dataset name (without the `-vN` suffix), store the version separately in `datasetVersion`, and keep the local cache filename versioned (for example, `...-v3.jsonl`). Persist the local `datasetFile` and remote `datasetUri` together so every evaluation suite can resolve both the cache artifact and the Foundry-registered dataset. Add a `tags` map to each suite (for example, `tier: smoke`, `purpose: baseline`) so workflows can group or filter suites without a fixed priority enum. Local dataset filenames should start with the selected environment's Foundry `agentName` from the selected metadata file, followed by stage and version suffixes, so related cache files stay grouped by agent. If `agentName` already encodes the environment (for example, `support-agent-dev`), do not append the environment key again. Keep `datasets/`, `evaluators/`, and `results/` shared at the `.foundry/` root even when multiple metadata files exist. Use evaluation-suite IDs in evaluation names, result folders, and regression summaries so the flow remains traceable.

## Sync Guidance

- Pull/refresh when the user asks, when the workflow detects missing local cache, or when remote versions clearly differ from local metadata.
- Push/register updates after the user confirms local changes that should be shared in Foundry.
- Record remote dataset names, versions, dataset URIs, and last sync timestamps in `.foundry/datasets/manifest.json` or the relevant metadata section.
