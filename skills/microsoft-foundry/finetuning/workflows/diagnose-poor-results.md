# Diagnosing Poor Results

When your fine-tuned model performs worse than expected, work through this checklist top-down (most common causes first).

## Diagnostic Table

| # | Symptom | Likely Cause | Fix |
|---|---------|-------------|-----|
| 1 | Training loss → 0, validation loss rises | Overfitting | 1) Deploy earlier checkpoint. 2) Reduce epochs. 3) Lower LR. 4) Add more diverse data. Overfitting ratio > 1.5 is concerning. |
| 2 | High correctness, low conciseness (or reverse) | Dataset style mismatch | **Verbose**: Add concise examples, use "Be concise" system prompt, filter to shortest correct examples. **Terse**: Add detailed examples, increase dataset with quality-filtered data. |
| 3 | Model seems good on spot-check but auto-eval is low | Evaluation rubric issue | Manually grade 10 examples vs. LLM judge. Check: Is judge model strong enough? Is rubric clear? Do reference answers match desired output? |
| 4 | Garbage, empty outputs, or errors | Deployment/client bug | Check: wrong model format (→ HTTP 500), `AzureOpenAI` on project endpoint (→ "api-version not allowed"), low capacity (→ timeouts), wrong deployment name. Test with curl. |
| 5 | RFT model scores below base model | RFT-specific issue | See RFT section below. |

## RFT-Specific Diagnosis

| Signal | Meaning | Fix |
|--------|---------|-----|
| Train-val grader gap > 0.2 | Model gaming the grader | Use stricter/more deterministic grader (Python execution > LLM judge) |
| Grader too easy | High grader scores but bad outputs | Add multi-criteria grading (syntax + semantic) |
| Grader too noisy | Random signal, no learning | Use deterministic grader or increase val set size |
| All of the above fail | RFT may not suit this task | Switch back to SFT |

## Escalation Path

If nothing above helps:

1. **Try a different base model** — some fine-tune better for certain tasks
2. **Increase dataset 2x-5x** with synthetic data
3. **Simplify the task** — fine-tune for a narrower sub-task first
4. **Try prompt engineering instead** — sometimes a well-crafted system prompt beats fine-tuning
5. **Combine approaches** — prompt engineering + fine-tuning together

## Red Flags: Don't Fine-Tune

- Base model already scores > 9.0 (minimal headroom)
- Task changes frequently (constant retraining needed)
- < 50 examples and can't generate synthetic data
- "Correct" output is highly subjective
