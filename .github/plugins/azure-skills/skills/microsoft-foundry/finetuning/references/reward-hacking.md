# Reward Hacking Prevention in RFT

## What Is Reward Hacking?

The model optimizes for the grader's scoring function rather than the actual task. The training grader becomes a proxy reward that diverges from true quality — the model games the proxy instead of improving.

**Core rule: Your training grader MUST produce the same ranking as your evaluation methodology.**

| If you evaluate with… | Then train with… | NOT with… |
|------------------------|------------------|-----------|
| LLM judge (semantic) | LLM judge | AST / regex / structural matching |
| Exact match | Exact match | Fuzzy or partial matching |
| Unit tests | Unit tests | Static analysis alone |

Misaligned graders are the #1 cause of reward hacking.

## Train-Val Gap Thresholds

| Train-Val Gap | Status | Action |
|---------------|--------|--------|
| ≤ 0.05 | ✅ Healthy | Continue training |
| 0.05–0.10 | ⚠️ Warning | Monitor closely, check outputs qualitatively |
| > 0.10 | 🛑 Stop | Stop training — reward hacking is likely |

## Pre-Training Checklist

1. **Baseline the grader**: Run training grader on base model outputs. Record scores as your floor.
2. **Cross-validate graders**: If training grader ≠ eval grader, generate 50 outputs, score with both, compute Spearman ρ. Proceed only if ρ ≥ 0.8. If ρ < 0.6, fix alignment first.
3. **Test hackability**: Generate 5 intentionally bad outputs that might score well. If grader scores any > 5/10, redesign it.
4. **Set gap threshold**: Monitor train-val gap every eval_interval. Stop if > 0.10.

## Grader Iteration Loop

When reward hacking is detected:

```
1. STOP the training run
        ↓
2. COLLECT "hacked" outputs (high train score, low eval score)
        ↓
3. ANALYZE what pattern the model exploited
   (structural mimicry? verbosity? keyword stuffing?)
        ↓
4. UPDATE the grader to penalize that pattern
        ↓
5. RE-BASELINE the updated grader on base model outputs
        ↓
6. RESTART training with the improved grader
```

## Red Flags Checklist

Investigate immediately if **any** are true:

- [ ] Train-val gap > 0.10
- [ ] Training reward increasing but eval quality stable or declining
- [ ] Model outputs are longer/more verbose than base model
- [ ] Outputs structurally match references but are semantically wrong
- [ ] Different LLM judges disagree on quality
- [ ] Conciseness/style scores dropping while correctness climbs
- [ ] Model produces "template" responses

## Key Principles

| Principle | Action |
|-----------|--------|
| Align graders | Training grader must rank outputs same as eval |
| Cross-validate first | Spearman ρ ≥ 0.8 between training and eval graders |
| Monitor train-val gap | ≤ 0.05 healthy, > 0.10 stop |
| Test hackability | Bad outputs should score < 5/10 |
| Prefer SFT when possible | Use RFT only for verifiable-answer tasks |
| Iterate graders, not models | Fix grader before restarting training |
