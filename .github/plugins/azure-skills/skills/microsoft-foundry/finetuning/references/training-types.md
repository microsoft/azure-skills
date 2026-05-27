# Training Types: SFT vs DPO vs RFT

## Decision Matrix

| Factor | SFT | DPO | RFT |
|--------|-----|-----|-----|
| **Best for** | Teaching a new skill or format | Aligning preferences/style | Improving reasoning chains |
| **Data needed** | Input–output pairs | Chosen/rejected pairs | Prompts + grading function |
| **Data volume** | 50–5,000 examples | 500–5,000 pairs | 200–2,000 prompts |
| **Effort to prepare data** | Low | High (need contrasting pairs) | Medium (need grader, not outputs) |
| **Risk of regression** | Low | Medium | High (sensitive to grader quality) |
| **Typical improvement** | 5–30% on task metrics | Subtle style/safety shifts | 0–15% on reasoning tasks |
| **Supported models** | Most models | Select models | o4-mini |

## When to Use Each

### SFT (Supervised Fine-Tuning)
- You have high-quality input–output pairs
- Task is well-defined (code generation, classification, extraction, summarization)
- You want reliable, repeatable outputs in a specific format or style
- **Key insight**: 300–500 high-quality examples often outperforms 1,500+ lower-quality ones

### DPO (Direct Preference Optimization)
- You want to adjust tone, verbosity, safety, or style
- You have examples of "good" and "bad" outputs for the same input
- SFT already works but outputs need refinement
- DPO-specific params: `beta` (default 0.1), `l2_multiplier` (default 0.1)

### RFT (Reinforcement Fine-Tuning)
- Task has objectively verifiable answers (code execution, math, logic)
- You can write a programmatic or LLM-based grader
- You want to improve the model's reasoning, not just its outputs
- **Critical**: RFT is extremely sensitive to grader quality. Train–val gap should be ≤ 0.05.

## Choosing a Path

```
├─ Do you have labeled input–output pairs?
│  ├─ Yes → SFT
│  └─ No
│     ├─ Can you write a grading function? → RFT
│     └─ Can you rank "good" vs "bad" outputs? → DPO
│
After SFT:
├─ Results good enough? → Ship it
├─ Need style refinement? → DPO on top of SFT model
└─ Reasoning needs improvement? → RFT (if model supports it)
```

## Model Compatibility (Azure AI Foundry)

| Model | SFT | DPO | RFT | Vision FT |
|-------|-----|-----|-----|-----------|
| gpt-4.1 | ✅ | ✅ | ❌ | ✅ |
| gpt-4.1-mini | ✅ | ❌ | ❌ | ❌ |
| gpt-4.1-nano | ✅ | ❌ | ❌ | ❌ |
| gpt-4o (2024-08-06) | ✅ | ✅ | ❌ | ✅ |
| gpt-4o-mini | ✅ | ❌ | ❌ | ❌ |
| o4-mini | ❌ | ❌ | ✅ | ❌ |
| gpt-5 | ❌ | ❌ | ✅ ⚠️ | ❌ |
| gpt-oss-20b | ✅ | ❌ | ❌ | ❌ |
| Ministral-3B | ✅ | ❌ | ❌ | ❌ |
| Llama-3.3-70B | ✅ | ❌ | ❌ | ❌ |
| Qwen-3-32B | ✅ | ❌ | ❌ | ❌ |

DPO can be applied on top of an already SFT-fine-tuned model. Vision fine-tuning follows the same SFT workflow but with image data in messages.

> ⚠️ **Feature flags**: GPT-5 RFT and agentic RFT with tool calling require access requests. Contact your Microsoft account team or request access through the Azure AI Foundry portal. o4-mini RFT without tools is generally available.

*Check Azure AI Foundry docs for the latest model availability.*
