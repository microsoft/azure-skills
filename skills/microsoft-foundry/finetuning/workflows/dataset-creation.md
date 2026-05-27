# Dataset Creation Workflow

Three paths to training data (these combine well: curate seeds → augment → generate at scale):

> If you already have data, skip to validation: `python scripts/validate/validate_sft.py your_data.jsonl`

## Approach 1: Manual Curation

Write examples by hand, collect from production logs, or adapt existing datasets.

**When to use:**
- You have real-world examples (production logs, support tickets, labeled data)
- Your task requires domain expertise an LLM can't reliably generate
- You need a gold-standard evaluation set (always curate manually)

**Tips:**
- Start with 10-20 examples to establish quality standards and format consistency
- These seed examples also serve as the foundation of your evaluation test set
- For RFT, you only need prompts + expected answers — no model responses needed

## Approach 2: LLM Augmentation

Expand a small curated dataset through **rephrasing** — generating diverse variations while keeping the same expected answer. Especially useful for RFT.

**When to use:**
- Well-defined task with clear correct answers
- You can write quality examples but need more volume
- Diversity of phrasing matters more than diversity of scenarios

**Workflow:**
1. Write base examples with correct expected answers
2. For each, use an LLM to generate rephrasings varying tone, detail, and wording
3. Each rephrasing gets the same expected answer — only the phrasing changes
4. Validate the augmented dataset

**Rephrasing prompt:**
```
Generate N different phrasings of this request. Each should:
- Use different wording, tone, or level of detail
- Include the same key identifiers (order IDs, item names)
- Vary between formal, casual, frustrated, brief, and detailed styles
Return a JSON array of N strings.

Original: [your example]
```

A cheap model (gpt-4.1-mini) works well — no new ground truth needed, just phrasing diversity.

## Approach 3: Synthetic Generation

Generate training data from scratch using LLM prompts.


1. Define topic/scenario categories for diversity
2. Generate prompts from an LLM
3. Generate responses (or preferred/non-preferred pairs for DPO)
4. Grade quality with an LLM judge
5. Filter to a quality threshold
6. Split into train/validation/test sets
7. Write JSONL in the correct format (see `references/dataset-formats.md`)

## Quality Checklist

Before training, verify:

- [ ] **No duplicates**: Exact or near-duplicate examples waste budget
- [ ] **Balanced distribution**: Topics, difficulty, output lengths well-distributed
- [ ] **Consistent formatting**: All examples follow the same structure
- [ ] **Correct outputs**: Spot-check 20 random examples manually
- [ ] **Reasonable lengths**: No extremely short or extremely long outputs
- [ ] **Clean text**: No encoding errors, garbled text, or template artifacts

## Dataset Size vs. Quality

From experiments:
- **335 high-quality examples** (carefully curated) → best combined eval score (9.15)
- **1,576 examples** (broader but noisier) → higher correctness but lower conciseness (8.53)

**Takeaway**: A small, pristine dataset usually beats a large, noisy one. Quality filter aggressively.
