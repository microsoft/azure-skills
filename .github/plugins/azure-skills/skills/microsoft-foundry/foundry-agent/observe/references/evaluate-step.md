# Step 2 - Run Evaluation

## Prerequisites

- Agent deployed and running in the selected environment
- Selected `.foundry/agent-metadata*.yaml` file loaded for the active agent root
- Evaluation suite selected from the environment's `evaluationSuites[]`
- For generated suites: `suiteName` present and verified with `evaluation_suite_get`
- For legacy suites: local dataset and evaluator metadata available in `.foundry/`

## Definition of Done — Evaluation Run

A Step 2 evaluation run is complete only when **every** box below is checked. Do **not** produce a final "evaluation complete" summary, score table, or report link until all items are done. "Status reached `completed`" is **not** a stopping condition — `evaluation_get` returns metadata only.

- [ ] `evaluation_agent_batch_eval_create` returned an `evalRunId`
- [ ] `evalId` and `evalRunId` mirrored into the selected `.foundry/agent-metadata*.yaml` (`environments.<env>.lastEval.{evalId, evalRunId, runName, suiteName, suiteVersion, agentVersion, startedAt}`) so a later turn can resume
- [ ] Polling reached terminal state (`completed`, `failed`, or `cancelled`)
- [ ] Per-item `output_items` downloaded via the `azure-ai-projects` Python SDK (see [Step 3 → Download Results](analyze-results.md#step-3--download-results)) — NOT via `evaluation_get`, NOT via `evaluation_dataset_sas_url_get`
- [ ] Results persisted under `.foundry/results/<env>/<eval-id>/<run-id>.json`
- [ ] Per-item failures and any `passed: null` / `reason: null` items have been clustered (Step 4) before summarizing

## Run Agent-Target Batch Eval

Use **`evaluation_agent_batch_eval_create`** for batch evaluation, even when the selected metadata entry was produced by evaluation-suite generation. Treat the generated suite as the reviewed source of dataset/evaluator metadata, not as the execution API.

| Parameter | Description |
|-----------|-------------|
| `projectEndpoint` | Azure AI Project endpoint from the selected metadata file |
| `agentName` | Agent name for the selected environment |
| `agentVersion` | Agent version (string, for example `"1"`) |
| `evaluatorNames` | Array of evaluator names from the selected evaluation suite |
| `evaluationName` | Include environment and evaluation-suite ID |
| `runName` | Include environment, suite ID, and agent version |
| `deploymentName` | Required for LLM-judge evaluators |
| `inputData` | Array of inline test items, each an object with a `query` string (and optional `expected_behavior`). **Required for agent-target runs unless `generateSyntheticData=true` is set.** The parameter name is `inputData` — not `data`, `inputItems`, or `inputDataItems`. |
| `generateSyntheticData` | Set `true` to skip `inputData` and let the service generate test queries. Requires `generationModelDeploymentName` and `samplesCount`. The service rejects requests with only `datasetName`/`datasetVersion`; it does not auto-resolve generated suite datasets into input rows. |
| `generationModelDeploymentName` | Model deployment used to generate synthetic queries when `generateSyntheticData=true`. |
| `samplesCount` | Number of synthetic queries to generate (15–1000). |
| `evaluationId` | Existing eval group ID, only when evaluator set and thresholds are unchanged |

Before the run, if the selected suite has `suiteName`, call `evaluation_suite_get(projectEndpoint, suiteName, version)` and confirm it references the expected dataset/evaluators. Use the suite to select evaluator names, thresholds, and local review artifacts, then run `evaluation_agent_batch_eval_create`. Run suites tagged `tier=smoke` first unless the user chooses a broader suite tag or a specific suite.

## Test Data

Use generated suite datasets for user review and lineage. For the agent-target batch eval tool:

- Pass test rows inline via the **`inputData`** parameter (array of `{query: "...", expected_behavior?: "..."}` objects). The service does not accept `datasetName`/`datasetVersion` references for agent-target runs — a generated suite dataset must be materialized into `inputData` rows by the caller.
- Reviewed local rows should include `expected_behavior` so adaptive evaluators and failure analysis can preserve the user's rubric.
- Alternatively, set `generateSyntheticData=true` with `generationModelDeploymentName`, `samplesCount` (15–1000), and optional `outputDatasetName` when the user wants the agent-target run to generate a fresh test set instead of supplying `inputData`.
- Do not call `evaluation_suite_run` for batch eval.

> ⚠️ **Parameter-name guardrail:** The inline-rows parameter is `inputData`. The service rejects `data`, `inputItems`, and `inputDataItems` with the misleading error `"At least one input data item must be provided ... Set generateSyntheticData=true to auto-generate test queries instead."` — that error means the rows were sent under the wrong key, not that synthetic generation is required.

Before setting `deploymentName`, use `model_deployment_get` to list actual project deployments and choose one that supports chat completions; do **not** assume `gpt-4o` exists.

## Parameter Naming Guardrail

| Tool | Correct Group Parameter | Notes |
|------|-------------------------|-------|
| `evaluation_agent_batch_eval_create` | `evaluationId` | Agent-target batch eval run grouping |
| `evaluation_get` | `evalId` | Use with `isRequestForRuns=true` to list runs in one group |
| `evaluation_comparison_create` | `insightRequest.request.evalId` | Comparison requests take `evalId`, not `evaluationId` |

`evaluation_get` does **not** accept `evaluationId`; switch to `evalId` after run creation.

> ⚠️ **Eval-group immutability:** Reuse an existing eval group only when dataset, evaluator list, and thresholds are unchanged. If evaluator definitions or thresholds change, create a new evaluation group or suite version.

## Auto-Poll for Completion

Immediately after creating the run, poll `evaluation_get` in a background terminal until completion. Use `evalId + isRequestForRuns=true` for run lists. The run ID parameter is `evalRunId` (not `runId`).

Only surface the final result when status reaches `completed`, `failed`, or `cancelled`.

> ⚠️ **`evaluation_get` returns run metadata only — it does NOT return per-item scores, agent responses, or judge reasons.** Once the run reaches terminal state, you MUST immediately follow [Step 3 → Download Results](analyze-results.md#step-3--download-results) and pull `output_items` via the `azure-ai-projects` Python SDK (`client.get_openai_client().evals.runs.output_items.list(...)`). Do **not** attempt to use `evaluation_dataset_sas_url_get` on the result artifact (`eval-result-<runId>-*`) — that endpoint is for evaluation **input** datasets and returns 500 for result artifacts.

> 💡 **Mirror IDs to metadata immediately.** Right after `evaluation_agent_batch_eval_create` returns, write `evalId`, `evalRunId`, `runName`, `suiteName`/`suiteVersion`, `agentVersion`, and `startedAt` to the selected environment's `lastEval` block in `.foundry/agent-metadata*.yaml`. This lets a later turn resume polling or downloading without re-reading chat history. The azd `.env` (`LAST_EVAL_ID`, etc.) is azd-internal and should not be relied on by skill flows.

## Background Polling Pattern

MCP tools live in the agent's process, so a true detached poller cannot call MCP tools directly. Use one of these concrete patterns instead of saying "ping me later":

1. **Sentinel-file poller (preferred for long-running jobs).** Spawn a sync terminal Python job that polls the Foundry REST API with the user's Azure credential (via `azure-identity` + `requests`) every 60–120s and writes status to `.foundry/.poll/<evalRunId>.json` when terminal. The next turn reads the sentinel file before doing anything else.
2. **Batched in-turn polling.** If a sentinel poller is unavailable, batch 2–4 poll calls per turn (60–120s apart, via short `sleep` between MCP calls in the same response) before yielding back to the user. Always explain that polling will continue on the next turn and update the metadata's `lastEval.lastPolledAt` so resumption is obvious.
3. **Never silently stop.** Returning "ping me later" without updating metadata or spawning a sentinel is a workflow violation — the user has to remember state for you.

## Next Steps

When evaluation completes -> immediately proceed to [Step 3: Analyze Results](analyze-results.md) and download `output_items`. Do not produce a summary first.

## Reference

- [Azure AI Foundry Cloud Evaluation](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/cloud-evaluation)
- [Built-in Evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators)
