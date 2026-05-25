# Evaluation Methodology

## Principles

1. **Always establish a baseline**: Evaluate the base (un-tuned) model first. Without a baseline, you can't measure improvement.
2. **Use a held-out test set**: Never evaluate on training or validation data. The model has seen those.
3. **Use the same test set for every model**: This is the only way to compare results fairly.
4. **Use task-specific graders**: Built-in generic evaluators (Coherence, Fluency) measure general quality and won't detect fine-tuning improvements. Use custom graders (Python, score model, string check) for task-specific evaluation.
5. **Measure cost alongside accuracy**: Report completion tokens per response when comparing models or checkpoints. A model that achieves the same accuracy with fewer tokens is strictly better — cheaper inference and lower latency.

## Two-Layer Evaluation Strategy

Use the **Azure AI Evaluation SDK** (`azure-ai-evaluation`) for all evaluation.

| Layer | Purpose | Grader Type | When |
|-------|---------|-------------|------|
| **Task-specific** (primary) | Measure FT improvement | `AzureOpenAIScoreModelGrader`, `AzureOpenAIPythonGrader`, `AzureOpenAIStringCheckGrader` | Every eval |
| **General quality** (guardrail) | Verify model didn't degrade | `CoherenceEvaluator`, `FluencyEvaluator` | Spot-check only |

Generic built-in evaluators (Coherence, Fluency, TaskAdherence) are guardrails, not metrics — they often show no difference between base and fine-tuned models even when domain-specific evaluation reveals clear improvement.

## Custom Graders (Primary FT Evaluation)

### 1. Score Model Grader (LLM judge with task-specific rubric)

Best for: subjective tasks (summarization, alignment, style).

```python
from azure.ai.evaluation import AzureOpenAIScoreModelGrader

summarization_grader = AzureOpenAIScoreModelGrader(
    model_config=model_config,
    name="summarization_quality",
    prompt="""Rate this news summary on a scale of 1-5.

Article: {{item.article}}
Summary: {{sample.output_text}}

Criteria:
- Captures ALL key facts (who, what, when, where)
- No hallucinated information not in the article
- Concise (under 3 sentences)

Score 1: Missing key facts or hallucinations
Score 3: Captures main point but misses details
Score 5: Perfect summary — all facts, no extras, concise

Return ONLY a number 1-5.""",
    output_type="numeric",
    pass_threshold=3,
)
```

### 2. Python Grader (programmatic/exact-match evaluation)

Best for: code generation, math, entity extraction, structured output.

```python
from azure.ai.evaluation import AzureOpenAIPythonGrader

entity_grader = AzureOpenAIPythonGrader(
    name="entity_extraction_accuracy",
    source="""
import json

def grade(item, sample):
    try:
        extracted = json.loads(sample["output_text"])
        reference = json.loads(item["ground_truth"])
    except (json.JSONDecodeError, KeyError):
        return {"score": 0, "reason": "Invalid JSON output"}

    required_keys = ["people", "organizations", "locations", "dates"]
    missing = [k for k in required_keys if k not in extracted]
    if missing:
        return {"score": 0.5, "reason": f"Missing keys: {missing}"}

    total, matched = 0, 0
    for key in required_keys:
        ref_set = set(str(v).lower() for v in reference.get(key, []))
        ext_set = set(str(v).lower() for v in extracted.get(key, []))
        total += len(ref_set)
        matched += len(ref_set & ext_set)

    score = matched / total if total > 0 else 1.0
    return {"score": score, "reason": f"{matched}/{total} entities matched"}
""",
    pass_threshold=0.7,
)
```

### 3. String Check Grader (pattern matching)

Best for: classification, format compliance, tool calling format.

```python
from azure.ai.evaluation import AzureOpenAIStringCheckGrader

tool_format_grader = AzureOpenAIStringCheckGrader(
    name="tool_call_format",
    input="{{sample.output_text}}",
    operation="like",          # or "eq", "starts_with", "contains"
    reference="function_call",
    pass_threshold=1,
)

classification_grader = AzureOpenAIStringCheckGrader(
    name="classification_accuracy",
    input="{{sample.output_text}}",
    operation="eq",
    reference="{{item.expected_label}}",
    pass_threshold=1,
)
```

## Running an Evaluation

The `evaluate()` function runs multiple graders over an entire dataset:

```python
from azure.ai.evaluation import evaluate, F1ScoreEvaluator

result = evaluate(
    data="eval_data.jsonl",
    evaluators={
        "task_grader": my_custom_score_grader,   # primary
        "f1": F1ScoreEvaluator(),                 # token overlap
    },
    output_path="./eval_results.json",
)

for metric, value in result["metrics"].items():
    print(f"{metric}: {value}")
```

## Test Set Design

- **Size**: 30–100 examples is sufficient.
- **Diversity**: Cover easy/medium/hard, edge cases, and different sub-categories.
- **Quality**: Reference answers must be gold-standard correct. A wrong reference penalizes correct outputs.

## Interpreting Results

| Score Type | Range | Meaning |
|-----------|-------|---------|
| AI quality (1–5) | 1–2 Poor, 3 Adequate, 4 Good, 5 Excellent | |
| NLP (0–1) | <0.3 Wrong, 0.3–0.6 Partial, 0.6–0.8 Good, >0.8 Strong | |

With 50+ eval examples, a difference of ~0.3 points (on 1–5 scale) is usually meaningful.

## Evaluating RFT Models

1. **Evaluate with a DIFFERENT rubric than the training grader** — otherwise you measure overfitting to the grader.
2. Use `F1ScoreEvaluator` for exact-match accuracy.
3. Use `SimilarityEvaluator` to catch semantically correct but differently formatted answers.
4. **Compare against the base model**, not just other fine-tunes.

## Reference

- [Azure AI Evaluation SDK docs](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-evaluation-readme)
- [Evaluation samples](https://github.com/Azure-Samples/azureai-samples/tree/main/scenarios/evaluate)
