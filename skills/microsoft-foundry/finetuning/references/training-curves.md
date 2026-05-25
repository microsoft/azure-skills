# Training Curve Analysis

## SFT Metrics

| Column | What it means |
|--------|---------------|
| `train_loss` | Loss on training batch (should decrease) |
| `train_mean_token_accuracy` | Token-level accuracy on training data |
| `valid_loss` | Loss on validation set (**primary metric**) |
| `valid_mean_token_accuracy` | Token-level accuracy on validation data |
| `full_valid_loss` | Full-pass validation loss (more accurate, less frequent) |
| `full_valid_mean_token_accuracy` | Full-pass token accuracy |

## Overfitting Detection

**Overfitting ratio** at each checkpoint: `valid_loss / train_loss`

| Ratio | Interpretation |
|-------|---------------|
| < 1.2 | Healthy — generalizes well |
| 1.2–1.5 | Mild overfitting — acceptable for small datasets |
| 1.5–2.0 | Moderate — consider reducing epochs |
| > 2.0 | Severe — deploy an earlier checkpoint |

```python
val_losses = [cp.metrics.valid_loss for cp in checkpoints if cp.metrics.valid_loss]
best_val = min(val_losses)
final_val = val_losses[-1]
if final_val > best_val * 1.2:
    print(f"⚠️ OVERFIT: Best={best_val:.4f}, final={final_val:.4f}")
```

## Best Checkpoint Selection (SFT)

```python
checkpoints = client.fine_tuning.jobs.checkpoints.list(job_id)
best_cp = min(checkpoints.data, key=lambda cp: cp.metrics.valid_loss or float('inf'))
print(f"Best: step {best_cp.step_number}, valid_loss={best_cp.metrics.valid_loss:.4f}, "
      f"model={best_cp.fine_tuned_model_checkpoint}")
```

## Diagnosis Table

| Observation | Diagnosis | Action |
|-------------|-----------|--------|
| Train loss barely decreases | LR too low or noisy data | Increase LR or clean data |
| Train loss crashes to ~0 | LR too high or easy data | Decrease LR or add harder examples |
| Valid loss rises after epoch 2 | Overfitting | Deploy epoch-2 checkpoint |
| Valid loss plateaus after epoch 1 | Learned quickly | Try epoch=1 or lower LR |
| Valid loss oscillates | Small batch or inconsistent data | Increase batch size or audit data |
| Both losses stay high | Task too hard | Larger model or simplify task |
| Large train-valid gap from start | Insufficient/mismatched data | Add diverse training data |

## RFT Metrics

| Column | What it means |
|--------|---------------|
| `train_mean_reward` | Average reward across rollouts (**primary** — should increase) |
| `full_valid_mean_reward` | Validation reward (overfitting check) |
| `completion_tokens_mean` | Average response length per rollout |
| `reasoning_tokens_mean` | Average reasoning tokens (o-series models) |
| `mean_unresponsive_rewards` | Rollouts with no scoreable output |
| `train_sample_parse_error_count` | Grader couldn't parse output |
| `train_other_error_count` | Grader logic bugs — should be 0 |

## RFT Reward Curve Patterns

- **Reward flat at ~0**: Grader broken or threshold too strict
- **Reward always negative**: pass_threshold too high
- **Reward immediately high + flat**: Threshold too lenient
- **Train-valid reward gap > 0.10**: Possible reward hacking

### Token Growth
- **Moderate** (tokens double): Normal — model becoming more thorough
- **Excessive** (3x+): Grader may incentivize verbosity — check scoring dimensions
- When comparing checkpoints, equal accuracy at fewer tokens is strictly better

### Parse Errors vs Logic Errors
- `sample_parse_error_count`: Often high in agentic RFT (mid-reasoning captures). Training still works if reward is climbing.
- `other_error_count`: Bugs in grader logic. Fix before continuing.

## RFT Checkpoint Selection

```python
checkpoints = client.fine_tuning.jobs.checkpoints.list(job_id)
for cp in checkpoints:
    m = cp.metrics
    tr = f"{m.train_mean_reward:.3f}" if m.train_mean_reward is not None else "n/a"
    vr = f"{m.full_valid_mean_reward:.3f}" if m.full_valid_mean_reward is not None else "n/a"
    ct = f"{m.completion_tokens_mean:.0f}" if m.completion_tokens_mean is not None else "n/a"
    print(f"Step {cp.step_number}: train_reward={tr}, valid_reward={vr}, tokens={ct}")
```

Don't rely solely on `valid_reward` for RFT — deploy 2–3 candidates (peak reward, final, mid-training) and evaluate with your real task harness including tool execution.
