# Agentic RFT — Tool Calling

Train reasoning models (o4-mini) for agentic scenarios where the model invokes external tools during chain-of-thought reasoning.

> ⚠️ **Access required**: Agentic RFT with tool calling and GPT-5 RFT are behind feature flags. You must request access through the Azure AI Foundry portal or your Microsoft account team. o4-mini RFT without tools is generally available.

## Tool Definition Format

```python
tools = [
    {
        "name": "search",
        "server_url": "https://your-function-app.azurewebsites.net/api/tools",
        "headers": {
            "Authorization": "Bearer <your-key>"
        }
    },
    {
        "name": "get_by_id",
        "server_url": "https://your-function-app.azurewebsites.net/api/tools",
        "headers": {
            "Authorization": "Bearer <your-key>"
        }
    }
]
```

## Submitting an Agentic RFT Job

```python
job = client.fine_tuning.jobs.create(
    model="o4-mini-2025-04-16",
    training_file=train.id,
    validation_file=valid.id,
    method={
        "type": "reinforcement",
        "reinforcement": {
            "grader": grader,
            "tools": tools,
            "max_episode_steps": 10,
            "hyperparameters": {
                "eval_interval": 5,
                "eval_samples": 10,
                "compute_multiplier": 1.5,
                "reasoning_effort": "medium"
            }
        }
    }
)
```

## Tool Response Format

Your tool endpoint must return:

```json
{
    "type": "function_call_output",
    "call_id": "call_12345xyz",
    "output": "The result of the tool call...",
    "id": "fc_12345xyz"
}
```

## Tool Endpoint Requirements

| Constraint | Limit |
|-----------|-------|
| Recommended throughput | 50 QPS |
| Max input payload | 1 MB |
| Max return payload | 1 MB (413 error if exceeded) |
| Timeout | 10 minutes |
| Parallel calls | Supported — handle race conditions |
| Retry on 5xx | 3 attempts, then rollout discarded |
| On 4xx | Error serialized and shown to model |

**Infrastructure**: Use Always On, sufficient compute (S2+), multiple instances. Under-provisioned endpoints can cause jobs to hang during post-training eval.

## RFT Hyperparameters

| Parameter | Description | Recommended Start |
|-----------|-------------|-------------------|
| `reasoning_effort` | `"low"`, `"medium"`, `"high"` | `"medium"` |
| `compute_multiplier` | Scales rollouts per step | `1.5` |
| `learning_rate_multiplier` | Scales the learning rate | `1.0` |
| `n_epochs` | Data passes | `2–3` |
| `eval_interval` | Eval every N steps | `5` |
| `eval_samples` | Validation examples per eval | `10` |
| `max_episode_steps` | Max tool calls + reasoning steps per rollout | `5–10` |

**Notes:** Higher LR increases output verbosity without improving accuracy. Compute multiplier 1.5 balances rollout quality and training time. Platform may early-stop before all epochs.

## When to Use Agentic RFT

- Model needs to **decide when to call tools** (not just follow instructions)
- Task involves **multi-step reasoning** with external data lookups
- Model needs to learn **tool selection** — choosing the right tool for the job
- Standard RFT (without tools) can't capture the agentic behavior
