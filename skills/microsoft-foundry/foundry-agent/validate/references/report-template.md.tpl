[Use this Markdown structure. Replace bracketed text.]

````markdown
# Microsoft Foundry Agent Validation

## Summary

**Report ID:** `[report ID]`<br>
**Hosted agent:** [service name]<br>
**Agent path:** [the unchanged agent path used for this validation run]<br>
**Generated:** [ISO date-time]

**Results:** [failed count] feedbacks · [passed count] passed · [inconclusive count] inconclusive · [not applicable count] not applicable

[Filter final JSON `results` into `fail`, `pass`, `inconclusive`, and `skipped` lists. Fill Summary from their exact lengths, never from a partial list. Omit zero-count statuses and require displayed counts to sum to `results.length`. Omit this table when there are no failed results.]

[Attach each result's original merged-rule index. Stable-sort every list by `(level rank, merged-rule index)` with `error=0`, `warning=1`, and `recommendation=2`. Use the sorted `fail` list for this table.]

| Level | Rule ID | Failed rule |
|---|---|---|
| [error | warning | recommendation] | `[rule ID]` | [rule title] |

[Create nonempty sections in this order: `fail` → `## Feedbacks`; `pass` → `## Passed checks`; `inconclusive` → `## Inconclusive`; `skipped` → `## Not applicable`. Render each list item exactly once in its matching section. Count the `- **Rule:**` blocks in each section; replace any differing Summary number before output.]

[After rendering, extract rule IDs from the table and each section. Compare them with the corresponding sorted list and correct any difference. Repeat this collapsed block for each result.]

<details>
<summary>[rule title]</summary>

- **Rule:** `[rule ID]`
- **Level:** [error | warning | recommendation]

#### Rationale

[Copy `rationale` from the rule.]

#### Source code

[Omit if absent. Render each array item as inline code, separated by `, `. Items use `file:line` or `file:start-end`.]

`main.py:7-9`, `infra/main.bicep:44`

#### Details

[For `fail`, explain the result and cite redacted `file:line` evidence when available. For `pass`, explain the evidence that proves the check passed. For `inconclusive`, explain why evidence cannot prove pass or fail and what is missing. For `skipped`, explain why the rule does not apply.]

#### Recommended action

[For `fail` only, state the concrete action required. Otherwise omit.]

#### Guidance

[Copy every guidance item exactly from the result without rewording, normalizing, or translating. Preserve object titles and links, and render legacy URL strings unchanged. Repeat each item.]

[For a `{ title, link }` object:]

- [guidance title](<[guidance link]>)

[For a legacy URL string:]

- <[guidance URL]>

</details>

## Limitation

This is an automated, repository-based best-practice review. It is not Microsoft certification, a compliance attestation, penetration testing, or validation of the deployed Azure environment.
````
