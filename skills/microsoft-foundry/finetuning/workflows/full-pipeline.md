# Full Pipeline Workflow

End-to-end fine-tuning on Azure AI Foundry in 9 phases.

## Prerequisites

- Azure AI Foundry resource with fine-tuning enabled
- Python 3.10+ with `openai` and `requests`
- Azure CLI (`az`) authenticated
- A clear task definition: what should the model do differently after fine-tuning?

## Phase 1: Define the Task

Answer before touching data or models:

1. **What task?** (e.g., "translate natural language to Python code")
2. **What does good output look like?** Write 5 examples by hand.
3. **What does bad output look like?** Write 3 anti-examples.
4. **How will you measure success?** Define evaluation dimensions (see `references/grader-design.md`).
5. **Which base model?** Pick 1-3 candidates from the supported model list.

## Phase 2: Prepare the Dataset

### Option A: You Have Data
1. Convert to SFT JSONL format (see `references/dataset-formats.md`)
2. Split: 80% train, 10% validation, 10% held-out test
3. Remove or fix low-quality examples

### Option B: Synthetic Data
1. Generate using LLM prompts (see `workflows/dataset-creation.md`)
2. Convert to SFT JSONL with `scripts/convert_dataset.py`

### Option C: Hybrid (Seed + Synthetic)
1. Use existing data as seed, generate synthetic variations
2. Merge, deduplicate, and quality-filter

**Checkpoint**: You should have `training.jsonl`, `validation.jsonl`, and `test.jsonl` (never used for training).

## Phase 3: Establish Baselines

1. Deploy base model (or use existing deployment)
2. Record scores — this is your "zero" that every fine-tune must beat

## Phase 4: Choose Training Type

See `references/training-types.md` for the full decision framework.

| Condition | Training Type |
|-----------|--------------|
| Have input-output pairs | SFT |
| Can write a grading function | RFT (reasoning models only) |
| Need style alignment | DPO |

Most projects start with SFT. Move to RFT/DPO only if SFT isn't sufficient.

## Phase 5: Upload and Submit Training

Use `scripts/submit_training.py` or the API directly. See `references/hyperparameters.md` for starting HP values.

**Foundry CLI** alternative (no Python):
```bash
azd ai finetuning jobs submit -f ./fine-tune-job.yaml
```

## Phase 6: Monitor and Analyze

1. Wait for completion or use `scripts/monitor_training.py`
2. Analyze training curves with `scripts/check_training.py`
3. Read `references/training-curves.md` to interpret results
4. Check for overfitting — consider deploying an earlier checkpoint if detected

## Phase 7: Evaluate Fine-Tuned Model

1. Deploy fine-tuned model (see `references/deployment.md` for format/SKU)
2. Compare against baseline and previous experiments
3. Delete deployment after evaluation

## Phase 8: Iterate

Follow `workflows/iterative-training.md`:
- Adjust hyperparameters based on training curves
- Try different data subsets or augmentations
- Test different base models
- Track everything in your leaderboard

## Phase 9: Ship

When the model convincingly beats baseline:
1. Deploy with production-appropriate capacity
2. Monitor with Application Insights
3. Periodically re-evaluate against test set for regression
4. Retrain as new data becomes available
