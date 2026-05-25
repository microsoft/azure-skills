# Quickstart: Fine-Tune Your First Model

6 steps from zero to a fine-tuned model using SFT with synthetic data.

> **Time**: ~20 min active + 1-3 hours training.

## Prerequisites

- Azure AI Foundry project with a deployed model (e.g., `gpt-4.1-mini`)
- Python 3.10+ with `openai` installed
- Project endpoint URL and API key (Foundry portal → Project Settings)

## Step 1: Connect to Your Project

```bash
export OPENAI_BASE_URL="https://<your-resource>.services.ai.azure.com/api/projects/<your-project>/openai/v1/"
export AZURE_OPENAI_API_KEY="<your-key>"
```

```python
from openai import OpenAI
import os

client = OpenAI(base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["AZURE_OPENAI_API_KEY"])
resp = client.chat.completions.create(model="gpt-4.1-mini", messages=[{"role": "user", "content": "Hello"}], max_tokens=10)
print(resp.choices[0].message.content)
```

## Step 2: Generate Training Data

```python
import json, re

SYSTEM_PROMPT = "You are a concise technical support agent. Answer in 1-2 sentences."

generation_prompt = """Generate 50 diverse technical support conversations.
Each should have a customer question and an ideal agent response (1-2 sentences).
Cover: password resets, billing, product setup, account changes, shipping, troubleshooting.
Return a JSON array where each element has "question" and "answer" fields."""

resp = client.chat.completions.create(
    model="gpt-4.1-mini", messages=[{"role": "user", "content": generation_prompt}],
    max_tokens=8000, temperature=1.0,
)

content = resp.choices[0].message.content
match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)
json_str = match.group(1) if match else content.strip().strip("`").replace("json\n", "")
examples = json.loads(json_str)

for split, name, rng in [("train", "train.jsonl", examples[:40]), ("val", "val.jsonl", examples[40:])]:
    with open(name, "w") as f:
        for ex in rng:
            f.write(json.dumps({"messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ex["question"]},
                {"role": "assistant", "content": ex["answer"]},
            ]}) + "\n")
```

Validate: `python scripts/validate/validate_sft.py train.jsonl`

## Step 3: Baseline the Base Model

```python
with open("val.jsonl") as f:
    test_examples = [json.loads(line) for line in f][:5]

for ex in test_examples:
    resp = client.chat.completions.create(
        model="gpt-4.1-mini", messages=ex["messages"][:2], max_tokens=200)
    print(f"Q: {ex['messages'][1]['content']}")
    print(f"Expected: {ex['messages'][2]['content']}")
    print(f"Base model: {resp.choices[0].message.content}\n")
```

## Step 4: Upload Data and Submit Job

```python
import time

with open("train.jsonl", "rb") as f:
    train = client.files.create(file=f, purpose="fine-tune")
with open("val.jsonl", "rb") as f:
    val = client.files.create(file=f, purpose="fine-tune")

for _ in range(30):
    if client.files.retrieve(train.id).status == "processed" and client.files.retrieve(val.id).status == "processed":
        break
    time.sleep(10)

job = client.fine_tuning.jobs.create(
    model="gpt-4.1-mini", training_file=train.id, validation_file=val.id,
    suffix="my-first-ft",
    method={"type": "supervised"},
    hyperparameters={"n_epochs": 2, "learning_rate_multiplier": 1.0},
)
print(f"Job submitted: {job.id}")
```

Or via script:
```bash
python scripts/submit_training.py --model gpt-4.1-mini --training-file train.jsonl --validation-file val.jsonl --type sft --suffix my-first-ft --epochs 2
```

## Step 5: Monitor

```bash
python scripts/monitor_training.py --job-id <your-job-id>
```

Or check [Azure AI Foundry portal](https://ai.azure.com) → Fine-tuning → Jobs.

## Step 6: Deploy, Test, and Compare

```bash
python scripts/deploy_model.py --model-id <fine-tuned-model-name> --name my-ft-deployment --capacity 50
```

```python
for ex in test_examples:
    base = client.chat.completions.create(model="gpt-4.1-mini", messages=ex["messages"][:2], max_tokens=200)
    ft = client.chat.completions.create(model="my-ft-deployment", messages=ex["messages"][:2], max_tokens=200)
    print(f"Q: {ex['messages'][1]['content']}")
    print(f"Base:       {base.choices[0].message.content}")
    print(f"Fine-tuned: {ft.choices[0].message.content}\n")
```

## What's Next

- **Scale data**: 200-500 examples → `workflows/dataset-creation.md`
- **Try RFT**: For verifiable answers → `references/training-types.md`
- **Debug**: `workflows/diagnose-poor-results.md`
- **Full guide**: `workflows/full-pipeline.md`
