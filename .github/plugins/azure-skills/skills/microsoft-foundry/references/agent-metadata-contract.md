# Agent Metadata Contract

Use this contract for every agent source folder that participates in Microsoft Foundry workflows.

## Required Local Layout

```text
<agent-root>/
  .foundry/
    agent-metadata.yaml
    agent-metadata.prod.yaml
    suites/
    datasets/
    evaluators/
    results/
```

- `agent-metadata.yaml` is the preferred local/dev metadata file.
- Optional sidecar files such as `agent-metadata.prod.yaml` can hold a single prod or CI-targeted environment without mixing multiple environments in one file.
- `suites/`, `datasets/`, and `evaluators/` are local cache folders. Reuse existing files when they are current, and ask before refreshing or overwriting user-edited files. Deterministic re-fetch of the same immutable remote `<name>-v<version>` may replace the generated cache artifact for that exact version.
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
| `environments.<name>.evaluationSuites[]` | ✅ | Foundry suite + dataset + local/remote references + evaluator + tag bundles for evaluation workflows |

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
        suiteName: support-agent-dev-smoke
        suiteVersion: "1"
        generationJobId: <suite-generation-job-id>
        generationSource: synthetic
        tags:
          tier: smoke
          purpose: baseline
          stage: seed
        dataset: support-agent-dev-eval-seed
        datasetVersion: v1
        suiteFile: .foundry/suites/support-agent-dev-smoke-v1.json
        datasetFile: .foundry/datasets/support-agent-dev-eval-seed-v1.ref.json
        datasetContentPath: .foundry/datasets/support-agent-dev-eval-seed-v1/
        datasetUri: <foundry-dataset-uri>
        evaluators:
          - name: intent_resolution
            threshold: 4
          - name: task_adherence
            threshold: 4
          - name: citation_quality
            version: "1"
            threshold: 0.9
            definitionFile: .foundry/evaluators/citation-quality-v1.json
      - id: trace-regression-suite
        suiteName: support-agent-dev-traces
        suiteVersion: "3"
        generationSource: traces
        tags:
          tier: regression
          purpose: regression
          stage: traces
        dataset: support-agent-dev-traces
        datasetVersion: v3
        suiteFile: .foundry/suites/support-agent-dev-traces-v3.json
        datasetFile: .foundry/datasets/support-agent-dev-traces-v3.ref.json
        datasetContentPath: .foundry/datasets/support-agent-dev-traces-v3/
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
        suiteName: support-agent-prod-guardrails
        suiteVersion: "2"
        generationSource: manual-fallback
        tags:
          tier: smoke
          purpose: safety
          stage: prod
        dataset: support-agent-prod-curated
        datasetVersion: v2
        suiteFile: .foundry/suites/support-agent-prod-guardrails-v2.json
        datasetFile: .foundry/datasets/support-agent-prod-curated-v2.ref.json
        datasetContentPath: .foundry/datasets/support-agent-prod-curated-v2/
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
| `suiteName`, `suiteVersion`, `generationJobId`, `generationSource`, `dataset`, `datasetVersion`, `datasetFile`, `datasetUri`, `evaluators` | Keep as-is |
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

Each evaluation suite should point to one dataset and one or more evaluators with explicit thresholds. Store `dataset` as the stable Foundry dataset name (without the `-vN` suffix), store the version separately in `datasetVersion`, and keep local cache filenames versioned (for example, `...-v3.ref.json`). Persist the local `suiteFile`, `datasetFile`, `datasetContentPath`, and remote `datasetUri` together so every evaluation suite can resolve both local cache artifacts and the Foundry-registered dataset. Add a `tags` map to each suite (for example, `tier: smoke`, `purpose: baseline`) so workflows can group or filter suites without a fixed priority enum. Local dataset filenames should start with the selected environment's Foundry `agentName` from the selected metadata file, followed by dataset and version suffixes, so related cache files stay grouped by agent. If `agentName` already encodes the environment (for example, `support-agent-dev`), do not append the environment key again. Keep `suites/`, `datasets/`, `evaluators/`, and `results/` shared at the `.foundry/` root even when multiple metadata files exist. Use evaluation-suite IDs in evaluation names, result folders, and regression summaries so the flow remains traceable.

For generated Foundry suites, also persist `suiteName`, `suiteVersion`, `generationJobId`, and `generationSource`. Valid `generationSource` values are `synthetic`, `traces`, `dataset`, `file`, `prompt`, and `manual-fallback`. A suite with `suiteName` should still run batch eval through `evaluation_agent_batch_eval_create`; use `evaluation_suite_get` only to resolve the reviewed dataset/evaluator metadata. Evaluator entries may include `version` and `definitionFile`; `definitionFile` points to the full cached evaluator JSON returned by `evaluator_catalog_get`. If the user creates a separate reviewed rubric file, store it in a distinct field such as `reviewedDefinitionFile`.

Example generated suite entry:

```yaml
evaluationSuites:
  - id: smoke-core
    suiteName: support-agent-dev-smoke
    suiteVersion: "1"
    generationJobId: <suite-generation-job-id>
    generationSource: synthetic
    tags:
      tier: smoke
      purpose: baseline
      stage: generated
    dataset: support-agent-dev-smoke-data
    datasetVersion: "1"
    suiteFile: .foundry/suites/support-agent-dev-smoke-v1.json
    datasetFile: .foundry/datasets/support-agent-dev-smoke-data-v1.ref.json
    datasetContentPath: .foundry/datasets/support-agent-dev-smoke-data-v1/
    datasetUri: <foundry-dataset-uri>
    evaluators:
      - name: support-agent-dev-adaptive
        version: "1"
        threshold: 4
        definitionFile: .foundry/evaluators/support-agent-dev-adaptive-v1.json
```

## Sync Guidance

- Pull/refresh when the user asks, when the workflow detects missing local cache, or when remote versions clearly differ from local metadata.
- Push/register updates after the user confirms local changes that should be shared in Foundry. Use `data_generation_job_create` for dataset regeneration, `evaluation_dataset_create` for approved dataset versions, `evaluator_generation_job_create` or `evaluator_catalog_update(createNewVersion: true)` for adaptive evaluator updates, and `evaluation_suite_create` for reviewed suite versions.
- Record remote dataset names, versions, dataset URIs, and last sync timestamps in `.foundry/datasets/manifest.json` or the relevant metadata section.
