# Eval Lineage — Full Traceability from Production to Deployment

Track the complete chain from production traces through dataset creation, evaluation runs, comparisons, and deployment decisions. Enables "why was this deployed?" audit queries and compliance reporting.

## Lineage Chain

```
Production Trace (App Insights)
    │ conversationId, responseId
    ▼
Dataset Version (.foundry/datasets/*.jsonl, environment-scoped)
    │ metadata.conversationId, metadata.harvestRule
    ▼
Evaluation Run (evaluation_agent_batch_eval_create)
    │ evaluationId when creating, evalId when querying, evalRunId
    ▼
Comparison (evaluation_comparison_create)
    │ insightId, baselineRunId, treatmentRunIds
    ▼
Deployment Decision (agent_update)
    │ agentVersion
    ▼
Production Trace (cycle repeats)
```

## Lineage Manifest

Track lineage in `.foundry/datasets/manifest.json`:

```json
{
  "datasets": [
    {
      "name": "support-bot-prod-traces",
      "file": "support-bot-prod-traces-v3.jsonl",
      "version": "v3",
      "tag": "prod",
      "source": "trace-harvest",
      "harvestRule": "error+latency",
      "timeRange": "2025-02-01 to 2025-02-07",
      "exampleCount": 63,
      "createdAt": "2025-02-08T10:00:00Z",
      "evalRuns": [
        {
          "evalId": "eval-group-001",
          "runId": "run-abc-123",
          "agentVersion": "3",
          "date": "2025-02-08T12:00:00Z",
          "status": "completed"
        },
        {
          "evalId": "eval-group-001",
          "runId": "run-def-456",
          "agentVersion": "4",
          "date": "2025-02-10T09:00:00Z",
          "status": "completed"
        }
      ],
      "comparisons": [
        {
          "insightId": "insight-xyz-789",
          "baselineRunId": "run-abc-123",
          "treatmentRunIds": ["run-def-456"],
          "result": "v4 improved on 3/5 metrics",
          "date": "2025-02-10T10:00:00Z"
        }
      ],
      "deployments": [
        {
          "agentVersion": "4",
          "deployedAt": "2025-02-10T14:00:00Z",
          "reason": "v4 improved coherence +25%, relevance +10% vs v3"
        }
      ]
    }
  ]
}
```

## Audit Queries

### "Why was version X deployed?"

1. Read `.foundry/datasets/manifest.json`
2. Find entries where `deployments[].agentVersion == X`
3. Show the comparison that justified the deployment
4. Show the dataset and eval runs that informed the comparison

### "What traces led to this dataset?"

1. Read the dataset JSONL file
2. Extract `metadata.conversationId` from each example
3. Look up each conversation in App Insights using the [trace skill](../../trace/trace.md)

### "What evaluation history does this agent have?"

1. Use **`evaluation_get`** to list all evaluation groups
2. For each group, list runs with `isRequestForRuns=true`
3. Build the timeline from [Eval Trending](eval-trending.md)
4. Show comparisons from **`evaluation_comparison_get`**

### "Did this dataset version catch any regressions?"

1. Find the dataset version in the manifest
2. Check `evalRuns` for runs that used this dataset
3. Check `comparisons` for any regression results
4. Cross-reference with `tag == "regression-<date>"` entries

## Maintaining Lineage

Update `.foundry/datasets/manifest.json` at each step:

| Event | Fields to Update |
|-------|-----------------|
| Dataset created | Add new entry with `name`, `version`, `source`, `exampleCount` |
| Evaluation run | Append to `evalRuns[]` with `evalId`, `runId`, `agentVersion` |
| Comparison | Append to `comparisons[]` with `insightId`, `result` |
| Deployment | Append to `deployments[]` with `agentVersion`, `reason` |
| Tag change | Update `tag` field |

> 💡 **Tip:** Store the evaluation group identifier as `evalId` in lineage/manifest records, even if the create call used the parameter name `evaluationId`.

## Next Steps

- **View metric trends** → [Eval Trending](eval-trending.md)
- **Check for regressions** → [Eval Regression](eval-regression.md)
- **Harvest new traces** → [Trace-to-Dataset](trace-to-dataset.md) (start the next cycle)
