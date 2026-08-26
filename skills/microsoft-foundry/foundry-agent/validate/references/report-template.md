# Microsoft Foundry Agent Validation

| Field | Value |
|---|---|
| Report ID | `YYYYMMDDTHHMMSSZ` |
| Service | service name |
| Hosted Agent Root | hosted-agent root directory |
| Generated | ISO date-time |

## Rule results

Create one subsection for each active rule:

### `RULE-ID`: Rule title

- **Level:** error / warning / recommendation
- **Status:** pass / fail / inconclusive / skipped
- **Guidance:** Render every URL from the rule's `guidance` array as a Markdown link.

#### Details

Explain the result, cite redacted `file:line` evidence when available, and state how to fix failures or what evidence is missing for inconclusive results.

Use `inconclusive` when evidence cannot establish either `pass` or `fail`.

## Limitation

This is an automated, repository-based best-practice review. It is not Microsoft certification, a compliance attestation, penetration testing, or validation of the deployed Azure environment.
