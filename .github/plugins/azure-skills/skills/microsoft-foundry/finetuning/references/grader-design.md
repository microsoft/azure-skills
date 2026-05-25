# RFT Grader Design Guide

## Grader Type Selection

| Grader Type | Best For | Tradeoffs |
|------------|---------|-----------|
| **Python grader** (default) | Most tasks incl. tool-calling. Accesses `output_text` and `output_tools`. | Can't call external APIs or execute code. |
| **Multi grader** | Combining multiple scoring dimensions. | `score_model` component adds LLM cost per rollout. |
| **Endpoint grader** | Tasks requiring external API calls (test suites, DB queries). | HTTP latency, scaling risk. Under-provisioned endpoints can hang jobs. |
| **String check** | Exact-match tasks (classification, yes/no, numeric). | Binary 0/1 only — no partial credit. |

Start with Python grader unless you need external API calls. Python graders are fast, deterministic, reliable, and tool-aware (`sample.output_tools` provides tool call metadata).

## Partial Credit Pattern

Binary pass/fail gives sparse reward. Decompose into 2–4 scored dimensions:

```python
def grade(sample, item):
    output_text = sample.get("output_text", "") or ""
    expected = item.get("expected_answer", "")
    
    score = 0.0
    
    # Core correctness (highest weight)
    if correct_action(output_text, expected):
        score += 0.4
    
    # Precision (exact amounts, specific values)
    score += 0.3 * precision_score(output_text, expected)
    
    # Reasoning quality (cited correct rules/facts)
    score += 0.2 * reasoning_score(output_text, expected)
    
    # Process quality (used the right tools)
    if used_correct_tools(sample.get("output_tools", [])):
        score += 0.1
    
    return round(min(score, 1.0), 3)
```

### Weight Guidelines

| Dimension | Typical Weight | Examples |
|-----------|---------------|----------|
| Core correctness | 0.3–0.5 | Right action/answer/classification |
| Precision | 0.2–0.3 | Exact amounts, correct format |
| Reasoning | 0.1–0.2 | Cited correct rules, justified decision |
| Process quality | 0.05–0.1 | Used right tools, followed steps |

## Threshold Calibration Workflow

The `pass_threshold` determines what score counts as pass vs fail — the most important RFT hyperparameter.

1. Run the **base model** on your training/validation set
2. Score every output with your grader
3. Compute pass rates at multiple thresholds:

```python
for threshold in [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95]:
    pass_rate = sum(1 for s in scores if s >= threshold) / len(scores)
    print(f"  @{threshold}: pass={pass_rate:.0%}, fail={1 - pass_rate:.0%}")
```

4. Choose where **25–50% of base model rollouts fail**:

| Failure Rate | Signal Quality |
|-------------|----------------|
| < 10% | ❌ Too easy — no learning signal |
| 10–25% | ⚠️ Weak signal |
| **25–50%** | ✅ Good — enough failures to learn from |
| 50–70% | ⚠️ Harsh — mostly negative reward |
| > 70% | ❌ Too hard — training may diverge |

**Always re-run calibration when you change your dataset.**

## Consistency Rules

When using multiple graders (Python for training, endpoint for debugging, local script for eval):

1. **Identical scoring logic** — same weights, keywords, dimension breakdown
2. **Identical default scores** — same behavior when no action found, no amounts expected
3. **Test with same examples** — run 10 samples through all graders and verify scores match

Mismatched scoring causes the model to learn different behavior than what your evaluation measures.
