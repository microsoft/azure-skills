# Dataset Formats

## SFT Format (Supervised Fine-Tuning)

Standard chat-completion JSONL. Each line: JSON object with `messages` array.

```jsonl
{"messages": [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "What is 2+2?"}, {"role": "assistant", "content": "4"}]}
```

**Rules:**
- Each line must be valid JSON
- `messages` must contain at least one `user` and one `assistant` message
- `system` message is optional but recommended
- Multi-turn supported: alternate `user`/`assistant`
- Last message must be `assistant` (that's what the model learns)

**Validation checklist:** `.jsonl` extension, valid JSON per line, every example has `messages`, every message has `role` and `content`, no empty `content`.

## DPO Format (Direct Preference Optimization)

Three top-level fields: `input`, `preferred_output`, `non_preferred_output`.

```jsonl
{"input": {"messages": [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Explain gravity."}]}, "preferred_output": [{"role": "assistant", "content": "Gravity is a fundamental force that attracts objects with mass toward each other."}], "non_preferred_output": [{"role": "assistant", "content": "Gravity is when stuff falls down."}]}
```

**Rules:**
- `input`: Object with `messages` array (system + user turns). May include `tools` and `parallel_tool_calls`.
- `preferred_output` / `non_preferred_output`: Array of messages (`assistant` or `tool` role only)
- Both must contain at least one `assistant` message
- Exactly two completions compared per example

**DPO REST API example:**
```json
{
  "model": "gpt-4.1-mini-2025-04-14",
  "training_file": "file-abc123",
  "method": {
    "type": "dpo",
    "dpo": { "beta": 0.1, "l2_multiplier": 0.1 }
  }
}
```

## RFT Format (Reinforcement Fine-Tuning)

Chat-completion format with key differences from SFT:

```jsonl
{"messages": [{"role": "user", "content": "Write a Python function to reverse a string."}], "reference_code": "def reverse_string(s):\n    return s[::-1]", "expected_output": "olleh"}
```

**Rules:**
- Last message **MUST** be `user` role (model generates its own response)
- Extra fields alongside `messages` are accessible to grader via `item.*`
- Both training and validation datasets are **required**
- ⚠️ Do NOT put `assistant` as last message — unlike SFT, RFT generates its own outputs

**API version**: Python graders require `api-version=2025-04-01-preview` or later.

**Grader types:** `string_check` (exact match), `text_similarity` (fuzzy/BLEU/ROUGE), `python` (custom function), `score_model` (LLM judge), `multi` (weighted combination).

**Python grader template:**
```python
def grade(sample, item):
    """
    sample: dict with 'output_text' (model's generation)
    item: dict with extra fields from JSONL
    Returns: float 0.0–1.0
    """
    output = sample.get("output_text", "")
    reference = item.get("reference_code", "")
    return score
```

**Python grader constraints:** 256KB code max, no network, 2GB memory, 1GB disk, 2min timeout.

**Grader field access:**
- `sample.output_text` → model's generation
- `sample.output_json` → structured output (if using response_format)
- `item.*` → extra JSONL fields
- Template variables: `{{item.field_name}}` — no spaces inside braces, no array indexing

## Converting Between Formats

- **SFT → RFT**: Strip assistant messages (RFT last message must be `user`), add grader reference fields. Use `scripts/convert_dataset.py --format rft`.
- **SFT → DPO**: Generate rejected responses (run base model on same prompts, intentionally degrade good outputs, or use human ranking).
- **DPO → SFT**: Extract chosen responses from the preferred output.
