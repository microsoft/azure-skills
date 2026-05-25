# Iterative Training Workflow

Systematically improve a fine-tuned model through successive experiments.

## The Core Loop

```
1. Train with current config
2. Analyze training curves
3. Evaluate on held-out set
4. Diagnose what to change
5. Plan next experiment
→ Better than baseline? → Good enough? → Ship it (or loop back to 4)
```

**Rule**: Change ONE variable per experiment.

## Experiment Tracking

| Run | Base model | Dataset | Epochs | LR | Batch | Best val_loss | Combined eval |
|-----|-----------|---------|--------|-----|-------|--------------|---------------|
| R1 | gpt-4.1-mini | v1 (335 ex) | 2 | 1.0 | default | 0.320 | 8.05 |
| R2 | gpt-4.1-mini | v1 (335 ex) | 2 | 0.5 | default | 0.310 | 9.15 |
| ... | ... | ... | ... | ... | ... | ... | ... |

## What to Try (Priority Order)

### Priority 1: Data Quality (highest leverage)
- **Fix inconsistencies**: Contradicting examples confuse the model
- **Add diversity**: Add examples for input types the model fails on
- **Reduce noise**: Remove "correct but not ideal" outputs

### Priority 2: Hyperparameters

See `references/hyperparameters.md` for full guide.

**Quick sweep strategy:**
1. Baseline: epochs=2, lr=1.0
2. Overfitting → lr=0.5 or epochs=1
3. Underfitting → lr=1.5 or epochs=3
4. Good LR found → try batch_size=16 or 32

### Priority 3: Base Model

| Model | Best for |
|-------|----------|
| gpt-4.1-mini | Best quality-per-dollar, most tasks |
| gpt-4.1-nano | Fastest inference, simple tasks |
| gpt-oss-20b | Large datasets, lowest absolute loss |
| Ministral-3B | Lightweight, fast inference |
| Qwen-3-32B, Llama-3.3-70B | Multilingual or specialized tasks |

### Priority 4: Training Type
- SFT plateaued + need better reasoning → RFT (if model supports it)
- Need style alignment → DPO
- See `references/training-types.md` before switching

## Diagnostic Decision Tree

```
Training curves healthy (no overfitting)?
├─ Yes
│  ├─ Eval improved? → Refine further
│  └─ Eval same/worse? → Data quality issue — filter or augment
└─ No (overfitting)
   ├─ Earlier checkpoint evals well? → Deploy that checkpoint
   ├─ Not severe → Reduce epochs or lower LR
   └─ Severe (ratio > 2.0)
      ├─ Dataset too small → Add more data
      └─ Dataset large → Lower LR dramatically (0.1-0.3)
```

## When to Stop

1. Beaten baseline by meaningful margin (>5%) and last 3 experiments didn't improve
2. Diminishing returns: each experiment improves < 0.1 points
3. Model is "good enough" for production
4. Budget exhausted (time or money)

## Multi-Model Strategy

Run the same dataset through 2-3 base models:
1. **gpt-4.1-mini** — primary candidate
2. **gpt-oss-20b** — large-dataset specialist (500+ examples)
3. **gpt-4.1-nano** — fast inference option

## Common Mistakes

1. Not establishing a baseline first
2. Changing multiple variables at once
3. Overfitting to the eval set (keep a separate final test set)
4. Ignoring training curves (they tell you what to change next)
5. More data without quality check (lower-quality data often makes things worse)
6. Not cleaning up old deployments (wastes quota and money)
