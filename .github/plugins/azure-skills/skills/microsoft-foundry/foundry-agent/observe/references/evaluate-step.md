# Step 2 — Create Batch Evaluation

## Prerequisites

- Agent deployed and running in the selected environment
- Selected `.foundry/agent-metadata*.yaml` file loaded for the active agent root
- Evaluators configured (from [Step 1](deploy-and-setup.md) or `.foundry/evaluators/`)
- Local test dataset available (from the selected agent root's `.foundry/datasets/`)
- Evaluation suite selected from the environment's `evaluationSuites[]`

## Run Evaluation

Use **`evaluation_agent_batch_eval_create`** to run the selected evaluation suite's evaluators against the selected environment's agent.

### Required Parameters

| Parameter | Description |
|-----------|-------------|
| `projectEndpoint` | Azure AI Project endpoint from the selected metadata file |
| `agentName` | Agent name for the selected environment |
| `agentVersion` | Agent version (string, for example `"1"`) |
| `evaluatorNames` | Array of evaluator names from the selected evaluation suite |

### Test Data Options

**Preferred — local dataset:** Read JSONL from `.foundry/datasets/` and pass via `inputData` (array of objects with `query` and `expected_behavior`, optionally `context`, `ground_truth`). Always use this when the referenced cache file exists.

**Fallback only — server-side synthetic data:** Set `generateSyntheticData=true` and provide `generationModelDeploymentName`. Only use this when the local cache is missing and the user explicitly requests a refresh-free synthetic run.

## Resolve Judge Deployment

Before setting `deploymentName`, use **`model_deployment_get`** to list the selected project's actual model deployments. Choose a deployment that supports chat completions and use that deployment name for quality evaluators. Do **not** assume `gpt-4o` exists. If the project has no chat-completions-capable deployment, stop and tell the user quality evaluators cannot run until one is available.

### Additional Parameters

| Parameter | When Needed |
|-----------|-------------|
| `deploymentName` | Required for quality evaluators (the LLM-judge model) |
| `evaluationId` | Pass existing eval group ID to group runs for comparison |
| `evaluationName` | Name for a new evaluation group; include environment and evaluation-suite ID |

> **Important:** Use `evaluationId` on `evaluation_agent_batch_eval_create` (not `evalId`) to group runs. Run suites tagged `tier=smoke` first unless the user chooses a broader suite tag or a specific suite.

> ⚠️ **Eval-group immutability:** Reuse an existing `evaluationId` only when the dataset comparison setup is unchanged for that group: same evaluator list and same thresholds. If evaluator definitions or thresholds change, create a **new** evaluation group instead of adding another run to the old one.

## Parameter Naming Guardrail

These eval tools use similar names for the same evaluation-group identifier. Match the parameter name to the tool exactly:

| Tool | Correct Group Parameter | Notes |
|------|-------------------------|-------|
| `evaluation_agent_batch_eval_create` | `evaluationId` | Reuse the existing group when creating a new run |
| `evaluation_get` | `evalId` | Use with `isRequestForRuns=true` to list runs in one group |
| `evaluation_comparison_create` | `insightRequest.request.evalId` | Comparison requests take `evalId`, not `evaluationId` |

> ⚠️ **Common mistake:** `evaluation_get` does **not** accept `evaluationId`. Always switch from `evaluationId` to `evalId` after the run is created.

## Auto-Poll for Completion

Immediately after creating the run, poll **`evaluation_get`** in a background terminal until completion. Use `evalId + isRequestForRuns=true`. The run ID parameter is `evalRunId` (not `runId`).

Only surface the final result when status reaches `completed`, `failed`, or `cancelled`.

## Next Steps

When evaluation completes -> proceed to [Step 3: Analyze Results](analyze-results.md).

## Reference

- [Azure AI Foundry Cloud Evaluation](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/cloud-evaluation)
- [Built-in Evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators)
