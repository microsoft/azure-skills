# Evaluation Datasets — Trace-to-Dataset Pipeline & Lifecycle Management

Manage the full lifecycle of evaluation datasets for a Foundry agent: harvesting production traces into the selected agent root's local `.foundry` cache, curating versioned test datasets, tracking evaluation quality over time, and syncing approved updates back to Foundry when needed.

## When to Use This Skill

USE FOR: create dataset from traces, harvest traces into dataset, build test dataset, dataset versioning, version my dataset, tag dataset, pin dataset version, organize datasets, dataset splits, curate test cases, review trace candidates, evaluation trending, metrics over time, eval regression, regression detection, compare evaluations over time, dataset comparison, evaluation lineage, trace to dataset pipeline, annotation review, production traces to test cases.

> ⚠️ **DO NOT manually run** KQL queries to extract datasets or call `evaluation_dataset_create` **without reading this skill first.** This skill defines the correct trace extraction patterns, schema transformation, cache rules, versioning conventions, and quality gates that raw tools do not enforce.

> 💡 **Tip:** This skill complements the [observe skill](../observe/observe.md) (eval-driven optimization loop) and the [trace skill](../trace/trace.md) (production trace analysis). Use this skill when you need to bridge traces and evaluations: turning production data into test cases and tracking evaluation quality over time.

## Quick Reference

| Property | Value |
|----------|-------|
| MCP server | `azure` |
| Key Foundry MCP tools | `evaluation_dataset_create`, `evaluation_dataset_get`, `evaluation_dataset_versions_get`, `evaluation_get`, `evaluation_comparison_create`, `evaluation_comparison_get` |
| Storage tools | `project_connection_list` (discover `AzureStorageAccount` connection), `project_connection_create` (add storage connection) |
| Azure services | Application Insights (via `monitor_resource_log_query`), Azure Blob Storage (dataset sync) |
| Prerequisites | Agent deployed, selected `.foundry/agent-metadata*.yaml` file available, App Insights connected |
| Local cache | `.foundry/datasets/`, `.foundry/results/`, `.foundry/evaluators/` |

## Entry Points

| User Intent | Start At |
|-------------|----------|
| "Create dataset from production traces" / "Harvest traces" | [Trace-to-Dataset Pipeline](references/trace-to-dataset.md) |
| "Version my dataset" / "Tag dataset" / "Pin dataset version" | [Dataset Versioning](references/dataset-versioning.md) |
| "Organize my datasets" / "Dataset splits" / "Filter datasets" | [Dataset Organization](references/dataset-organization.md) |
| "Review trace candidates" / "Curate test cases" | [Dataset Curation](references/dataset-curation.md) |
| "Show eval metrics over time" / "Evaluation trending" | [Eval Trending](references/eval-trending.md) |
| "Did my agent regress?" / "Regression detection" | [Eval Regression](references/eval-regression.md) |
| "Compare datasets" / "Experiment comparison" / "A/B test" | [Dataset Comparison](references/dataset-comparison.md) |
| "Sync dataset to Foundry" / "Refresh local dataset cache" | [Trace-to-Dataset Pipeline -> Step 5](references/trace-to-dataset.md#step-5--sync-local-cache-with-foundry-optional) |
| "Trace my evaluation lineage" / "Audit eval history" | [Eval Lineage](references/eval-lineage.md) |
| "Generate eval dataset" / "Create seed dataset" / "Generate test cases for my agent" | [Generate Seed Dataset](references/generate-seed-dataset.md) |

## Before Starting — Detect Current State

1. Resolve the target agent root, selected metadata file, and environment from `.foundry/agent-metadata*.yaml`.
2. Confirm the selected environment's `projectEndpoint`, `agentName`, and observability settings.
3. Check `.foundry/datasets/`, `.foundry/results/`, and `.foundry/datasets/manifest.json` in the selected agent root only.
4. Check whether `evaluation_dataset_get` returns server-side datasets for the same environment.
5. Route to the appropriate entry point based on user intent.

## The Foundry Flywheel

```text
Production Agent -> [1] Trace (App Insights + OTel)
                -> [2] Harvest (KQL extraction)
                -> [3] Curate (human review)
                -> [4] Dataset Cache (.foundry/datasets, versioned)
                -> [5] Sync to Foundry (optional refresh/push)
                -> [6] Evaluate (batch eval)
                -> [7] Analyze (trending + regression)
                -> [8] Compare (agent versions OR dataset versions)
                -> [9] Deploy -> back to [1]
```

Each cycle makes the test suite harder and more representative. Production failures from release N become regression tests for release N+1.

## Behavioral Rules

1. **Always show KQL queries.** Before executing any trace extraction query, display it in a code block. Never run queries silently.
2. **Scope to time ranges.** Always include a time range in KQL queries (default: last 7 days for trace harvesting). Ask the user for the range if not specified.
3. **Require human review.** Never auto-commit harvested traces to a dataset without showing candidates to the user first. The curation step is mandatory.
4. **Use dataset naming conventions.** Follow the naming conventions below and keep local filenames aligned with the registered Foundry dataset name/version.
5. **Treat local files as cache.** Reuse `.foundry/datasets/` and `.foundry/evaluators/` when they already match the selected environment in the selected agent root. Offer refresh when the user asks or when remote state has changed.
6. **Stay inside the selected agent root.** After resolving the agent root, inspect only that folder's `.foundry/` cache and source context. Never merge sibling agent folders.
7. **Persist artifacts.** Save datasets to `.foundry/datasets/`, evaluation results to `.foundry/results/`, and track lineage in `.foundry/datasets/manifest.json`.
8. **Keep evaluation suites aligned.** Update the selected environment's `evaluationSuites[]` in the selected metadata file whenever a dataset version, evaluator set, or suite tags change. Local flows should default to `agent-metadata.yaml`; prod or CI-targeted flows can use `agent-metadata.<env>.yaml`. If the environment still uses older `testSuites[]` or legacy `testCases[]`, treat that list as the current suite source for this session and rewrite it as `evaluationSuites[]` on the next metadata save.
9. **Confirm before overwriting.** If a dataset version or cache file already exists, warn the user and ask for confirmation before replacing or refreshing it.
10. **Sync to Foundry when requested or needed.** After saving datasets locally, refresh or register them in Foundry only when the user asks or the workflow needs shared/CI usage.
11. **Never remove dataset rows or weaken evaluators to recover scores.** Score drops after a dataset update are expected - harder tests expose real gaps. Optimize the agent for new failure patterns; do not shrink the test suite.
12. **Match eval parameter names exactly.** Use `evaluationId` when creating grouped runs, but use `evalId` for `evaluation_get` and comparison/trending lookups.

## Dataset Naming and Metadata Conventions

| Dataset type | Foundry dataset name | Foundry dataset version | Typical local file | Metadata stage |
|--------------|----------------------|-------------------------|--------------------|----------------|
| Seed dataset | `<agent-name>-eval-seed` | `v1` | `.foundry/datasets/<agent-name>-eval-seed-v1.jsonl` | `seed` |
| Trace-harvested dataset | `<agent-name>-traces` | `v<N>` | `.foundry/datasets/<agent-name>-traces-v<N>.jsonl` | `traces` |
| Curated/refined dataset | `<agent-name>-curated` | `v<N>` | `.foundry/datasets/<agent-name>-curated-v<N>.jsonl` | `curated` |
| Production-ready dataset | `<agent-name>-prod` | `v<N>` | `.foundry/datasets/<agent-name>-prod-v<N>.jsonl` | `prod` |

Here `<agent-name>` means the selected environment's `environments.<env>.agentName` from the selected metadata file. If that deployed agent name already includes the environment (for example, `support-agent-dev`), do **not** append the environment key a second time.

Local dataset filenames must start with the selected Foundry agent name (`environments.<env>.agentName` in the selected metadata file). Put stage and version suffixes **after** that prefix so cache files sort and group by agent first.

Keep the Foundry dataset name stable across versions. Store the version only in `datasetVersion` (or manifest `version`) using the `v<N>` format, while local filenames keep the `-v<N>` suffix for cache readability.

Required metadata to track with every registered dataset:

- `agent`: the agent name (for example, `hosted-agent-051-001`)
- `stage`: `seed`, `traces`, `curated`, or `prod`
- `version`: version string such as `v1`, `v2`, or `v3`
- `datasetUri`: always persist the Foundry dataset URI in the selected metadata file alongside the local `datasetFile`, dataset name, and version

> 💡 **Tip:** `evaluation_dataset_create` does not expose a first-class `tags` parameter in the current MCP surface. Persist `agent`, `stage`, and `version` in local metadata (the selected metadata file plus `.foundry/datasets/manifest.json`) so Foundry-side references stay aligned with the cache.

## Related Skills

| User Intent | Skill |
|-------------|-------|
| "Run an evaluation" / "Optimize my agent" | [observe skill](../observe/observe.md) |
| "Search traces" / "Analyze failures" / "Latency analysis" | [trace skill](../trace/trace.md) |
| "Find eval scores for a response ID" / "Link eval results to traces" | [trace skill -> Eval Correlation](../trace/references/eval-correlation.md) |
| "Deploy my agent" | [deploy skill](../deploy/deploy.md) |
| "Debug container issues" | [troubleshoot skill](../troubleshoot/troubleshoot.md) |
| "Review metadata schema" | [Agent Metadata Contract](../../references/agent-metadata-contract.md) |
