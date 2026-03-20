# Agent Metadata Contract

Use this contract for every agent source folder that participates in Microsoft Foundry workflows.

## Required Local Layout

```text
<agent-root>/
  .foundry/
    agent-metadata.yaml
    datasets/
    evaluators/
    results/
```

- `agent-metadata.yaml` is the required source of truth for environment-specific Foundry configuration.
- `datasets/` and `evaluators/` are local cache folders. Reuse existing files when they are current, and ask before refreshing or overwriting them.
- `results/` stores local evaluation outputs and comparison artifacts by environment.

## Environment Model

| Field | Required | Purpose |
|-------|----------|---------|
| `defaultEnvironment` | ✅ | Environment used when the user does not choose one explicitly |
| `environments.<name>.projectEndpoint` | ✅ | Foundry project endpoint for that environment |
| `environments.<name>.agentName` | ✅ | Deployed Foundry agent name |
| `environments.<name>.azureContainerRegistry` | ✅ for hosted agents | ACR used for deployment and image refresh |
| `environments.<name>.observability.applicationInsightsResourceId` | Recommended | App Insights resource for trace workflows |
| `environments.<name>.observability.applicationInsightsConnectionString` | Optional | Connection string when needed for tooling |
| `environments.<name>.testCases[]` | ✅ | Dataset + local/remote references + evaluator + threshold bundles for evaluation workflows |

## Example `agent-metadata.yaml`

```yaml
defaultEnvironment: dev
environments:
  dev:
    projectEndpoint: https://contoso.services.ai.azure.com/api/projects/support-dev
    agentName: support-agent-dev
    azureContainerRegistry: contosoregistry.azurecr.io
    observability:
      applicationInsightsResourceId: /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Insights/components/support-dev-ai
    testCases:
      - id: smoke-core
        priority: P0
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
      - id: trace-regressions
        priority: P1
        dataset: support-agent-dev-traces
        datasetVersion: v3
        datasetFile: .foundry/datasets/support-agent-dev-traces-v3.jsonl
        datasetUri: <foundry-dataset-uri>
        evaluators:
          - name: coherence
            threshold: 4
          - name: groundedness
            threshold: 4
  prod:
    projectEndpoint: https://contoso.services.ai.azure.com/api/projects/support-prod
    agentName: support-agent-prod
    azureContainerRegistry: contosoregistry.azurecr.io
    testCases:
      - id: production-guardrails
        priority: P0
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

1. Auto-discover agent roots by searching for `.foundry/agent-metadata.yaml`.
2. If exactly one agent root is found, use it. If multiple roots are found, require the user to choose one.
3. Resolve environment in this order: explicit user choice, remembered session choice, `defaultEnvironment`.
4. Keep the selected agent root and environment visible in every deploy, eval, dataset, and trace summary.
5. Treat `datasets/` and `evaluators/` as cache folders. Reuse local files when present, but offer refresh when the user asks or when remote state is newer.
6. Never overwrite cache files or metadata silently.

## Test-Case Guidance

| Priority | Meaning | Typical Use |
|----------|---------|-------------|
| `P0` | Must-pass gate | Smoke checks, safety, deployment blockers |
| `P1` | High-value regression coverage | Production trace regressions, key business flows |
| `P2` | Broader quality coverage | Long-tail scenarios, exploratory quality checks |

Each test case should point to one dataset and one or more evaluators with explicit thresholds. Store `dataset` as the stable Foundry dataset name (without the `-vN` suffix), store the version separately in `datasetVersion`, and keep the local cache filename versioned (for example, `...-v3.jsonl`). Persist the local `datasetFile` and remote `datasetUri` together so every test case can resolve both the cache artifact and the Foundry-registered dataset. Local dataset filenames should start with the selected environment's Foundry `agentName`, followed by stage and version suffixes, so related cache files stay grouped by agent. If `agentName` already encodes the environment (for example, `support-agent-dev`), do not append the environment key again. Use test-case IDs in evaluation names, result folders, and regression summaries so the flow remains traceable.

## Sync Guidance

- Pull/refresh when the user asks, when the workflow detects missing local cache, or when remote versions clearly differ from local metadata.
- Push/register updates after the user confirms local changes that should be shared in Foundry.
- Record remote dataset names, versions, dataset URIs, and last sync timestamps in `.foundry/datasets/manifest.json` or the relevant metadata section.
