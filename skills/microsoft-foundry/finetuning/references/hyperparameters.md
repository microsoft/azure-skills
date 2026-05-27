# Hyperparameter Guide

## SFT / DPO Core Parameters

| Parameter | What it controls | Default | Typical range |
|-----------|-----------------|---------|---------------|
| **Epochs** | Passes through data | 2 | 1–5 |
| **Learning rate multiplier** | Weight change aggressiveness | 1.0 | 0.1–2.0 |
| **Batch size** | Examples per gradient step | Model-dependent | 4–32 |

### Dataset Size vs Epochs

| Dataset size | Recommended epochs |
|-------------|-------------------|
| < 100 examples | 3–5 |
| 100–500 examples | 2–3 |
| 500–2,000 examples | 1–2 |
| > 2,000 examples | 1 |

### Learning Rate Guidelines
- **Higher LR** (1.5–2.0): Large/diverse datasets, task very different from pre-training
- **Lower LR** (0.1–0.5): Small datasets (<200), refining not overwriting base behavior
- For 1,000+ examples, LR 0.2–0.5 often beats default 1.0

### DPO-Specific Parameters
- `beta` (default 0.1): Alignment strength. Lower = more conservative.
- `l2_multiplier` (default 0.1): Regularization to prevent drift from base model.

## HP Sweep Strategy

| Run | Epochs | LR | Why |
|-----|--------|----|-----|
| 1 | 2 | 1.0 | Baseline |
| 2 | 2 | 0.5 | Conservative |
| 3 | 2 | 1.5 | Aggressive |
| 4 | 3 | 1.0 | More training |
| 5 | 1 | 1.0 | Minimal intervention |

## Checkpoint Trick

When overfitting (val loss rises after epoch 2): deploy the epoch-2 checkpoint directly instead of retraining. Azure saves checkpoints at each epoch boundary.

```python
checkpoints = client.fine_tuning.jobs.checkpoints.list(job_id)
for cp in checkpoints.data:
    print(f"Step {cp.step_number}: val_loss={cp.metrics.valid_loss}")
```

## Model-Specific Recommendations

| Model | Recommended Start | Notes |
|-------|------------------|-------|
| gpt-4.1-mini | 2ep, lr=0.5–1.0 | Very capable base; small nudges work |
| gpt-4.1-nano | 2–3ep, lr=1.0–1.5 | Smaller capacity, needs more epochs |
| gpt-oss-20b | 2ep, lr=0.2–0.5 | Lower LR critical; deployment may need capacity=100 |
| o4-mini (RFT) | Grader quality > HPs | Focus on grader, not HP sweep |

## OSS Model Parameters

All OSS models require `trainingType: "globalStandard"` in the API request.

| Model | Recommended Start | Best Found | Notes |
|-------|------------------|------------|-------|
| Ministral-3B | 5ep, lr=1.0 | 10ep, lr=0.5 | Small model, slow convergence |
| gpt-oss-20b | 2ep, lr=0.3 | 2ep, lr=0.3 | lr=1.0 overfits quickly |
| Llama-3.3-70B | 3ep, lr=0.3 | 5ep, lr=0.5 | lr=2.0 causes catastrophic degradation |
| Qwen-3-32B | 3ep, lr=0.3 | 3ep, lr=0.3 | Most fragile — more data can hurt |

**Key patterns**: OSS models need 2–5× more epochs than nano. Lower LR (0.3–0.5) is safer. More data doesn't always help.

## RFT Hyperparameters

| Parameter | Description | Recommended Start |
|-----------|-------------|-------------------|
| `reasoning_effort` | `"low"`, `"medium"`, `"high"` | `"medium"` |
| `compute_multiplier` | Scales rollouts per step | `1.5` |
| `learning_rate_multiplier` | Scales LR | `1.0` |
| `n_epochs` | Data passes | `2–3` |
| `eval_interval` | Eval every N steps | `5` |
| `eval_samples` | Validation examples per eval | `10` |
| `max_episode_steps` | Max tool calls + reasoning steps | `5–10` |
