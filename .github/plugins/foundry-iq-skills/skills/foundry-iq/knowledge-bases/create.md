# Create a knowledge base

## When to use

Create exactly one KB over one verified File, Blob or ADLS Gen2 source.
Single-source helper; Azure supports multiple sources.

## Do not use

Not multiple sources, unsupported connectors, classic Search or agents.
Never mutate conflicts, select duplicates or call GA extraction synthesis.

## Inputs and discovery order

Reuse prompt/session/workspace/exact Azure readback; then one focused
question. Label sources; silence is not approval. Reads need no approval.

| Input | Why needed | Required? | Discovery order | Safe default | If missing or unanswered | Reconfirmation trigger |
|---|---|---|---|---|---|---|
| Tenant/subscription/group/region | Scope | Yes | Azure/selection | Propose absent group | Ask | Scope |
| Search ID/endpoint | Target | Pre-source | Discovery/bootstrap | Honor reuse/new | Bootstrap absent | Target |
| Source ID/type/boundary/definition | Grounding | Pre-approval | Source GET | None | Create absent; block unverified | Source |
| Base name/owner/purpose | Identity | Yes | Prompt/caller/GET | [Azure user](../references/owner.md) | Override | Identity/owner |
| Outcome/API/mode | Response | Yes | Prompt/GET | GA Blob: minimal/extractive | Block unsupported | Outcome/API |
| Effort/model/version/capacity | Preview | Conditional | Choice/bootstrap | Minimal/extractive | Resolve | Model/capacity/region |
| Caller/roles | Retrieval | Pre-query | Discovery/bootstrap | Service reader | Plan missing roles | Identity/scope |
| Network/permissions | Security | Required | Source/Search GET | Preserve | Block | Posture |
| Source identity | Source binding | Required | Source inventory | None | Block | Identity change |
| Acceptance/unrelated questions | Retrieval audit | Opt-in | Authorized evidence | Not requested | Defer audit | Question change |
| Cleanup owner | Recovery | Yes | Prompt, session | Cleanup not approved | Block | Owner change |

## Decisions

Offline audit is **opt-in**; no Q&A required for creation.
Propose title/content questions from authorized content, not filenames/structural facts.
No samples/questions: defer audit; separate query consent.
[Audit/filename](../helpers/retrieval-verification-contracts.md).

Default explicitly to minimal/extractive.
Minimal extractive KB adds no model; preview minimal permits synthesis.
Low/medium or synthesis needs a KB model, separate from source CU/embeddings.
Omitted KB/request effort defaults to `low`, not the portal's Minimal selection.
Retrieval/answer instructions: optional, preview-only. API `auto`: explicit handoff.

Select/recheck Search operation first: [owner](../search-services/create.md).
For low/medium or synthesis, select/reuse chat or
[bootstrap](../references/search-substrate.md) approved model/version/region/capacity/cost/access.
Verify readiness, resume KB creation; never downgrade.
Other infrastructure stays shared; no routine policy reads.

Retain source IDs/API/boundary/definition, ownership/health/permissions/reuse,
content assessment/uncertainty, answer needs and ingestion mode through prerequisites;
resume KB plus validated retrieval, not source-only. Readback drift blocks.
Only then present the KB plan; never preapprove a future `verified_source`
or reuse bootstrap consent for KB mutation.

GET exact name; only FIND paginates. Normalized match: zero-write.
Multiple compatible KBs require exact-ID selection. Same-name conflict/inaccessible blocks.
Choose:

- `minimal`: direct extractive grounding. Blob-only, non-agentic,
  non-permission-preview work defaults to GA `2026-04-01`, with no preview-only
  fields or synthesized `I don't know`.
- Preview minimal: explicit minimal effort; extractive or synthesis with one chat model.
  Synthesis adds model cost, not query planning; retrieval still uses `intents`.
- Low/medium: one preflighted chat model; `extractiveData` or `answerSynthesis`.
  Low is one-pass; medium may follow up. Preserve a low miss and ask one tradeoff
  question; never auto-escalate.

File/synthesis/permissions/low/medium require approved preview.
Prompt uses preview; GA MCP is minimal/extractive.

### Agent-compatible minimal transition

Optional, not a required step for every agent connection; preserve valid KB reasoning/synthesis.
Read the existing GA minimal KB through `2026-08-01-preview`; verify its source.
With separate approval, use `action: update` and the current ETag to set only
`outputMode: extractiveData` and `retrievalReasoningEffort: {kind: minimal}`.
Leave models, source contents, RBAC and networking unchanged;
preserve unrelated fields; conflicts block.
Verify agent MCP retrieval; GA isn't MCP proof.

## Proposed plan

Read [helper contracts](../helpers/contracts.md) before planning.
Use [KB intent/wire](../helpers/kb-contracts.md):
`python helpers/search_reconcile.py --plan <intent.json>`.
Show IDs/source/owner/API/mode/model, data/access/cost, optional acceptance,
actions/verification/cleanup/retained resources. No write.

## Confirmation

Keep immutable proposed mutation plan/`plan_fingerprint`, `cleanup_approved: false`.
Approve concrete changes once.
Changed source/mode/model/boundary/access, acceptance or freshness requires review;
never ask users to calculate or repeat hashes.

## Mutation

After approval, invoke:

```text
python helpers/search_reconcile.py --input <approved-envelope.json>
```

`reconcile`/`knowledge-base` binds endpoint/name/API/definition/owner,
`cleanup_approved: false`, verified source name/normalized same-API digest.
Before create/update/reuse, a fresh source GET must match.
Block absent/unreadable/drift, mode/API mixing and extra sources.
Conditional create/ETag-update reads back. Exit `2`: blocked/no-write;
`3`: partial.

Preserve API settings and reuse roles/dependencies. Never overwrite conflicts,
add sources, resize models, broaden access or modify source/generated children.
Resolve ambiguity on the same identity.

## Verification

Verify owner/source/API/mode/model/keyless access/roles/network.
Use REST [Retrieve](retrieve.md) with consent; check grounding/native references/activity, no MCP.
Errors remain incomplete.
Without query consent: `retrieval_status: not-tested`; KB creation is separate.
Requested retrieval stays incomplete until verified.
Default `audit_status: not-requested`; no paired bundle required.
Opted-in audits: original File path plus file ID or Blob/ADLS URL/path plus
ETag/version; a bare path/URL is insufficient. Missing proof stays unverified.
For authorized unrelated questions, `answerSynthesis` requires semantic abstention per the
[abstention criteria](retrieve.md#verification) and any explicit exact-output contract.
GA/preview `extractiveData` requires no supporting extracts.
Recheck stable IDs/zero writes.
Optional: [Connect](../agents/connect.md).

## Failure and partial completion

Preserve first status/message/request ID. Low failure never authorizes medium.
Citation/access/model/region/definition/source mismatch blocks.
`blocked`: evidence, no writes, next decision.
`partial`: writes, unverified state, ownership and separately approved cleanup.

## Cleanup

[Receipts](../lifecycle/cleanup.md): retain pre-create.
Separate cleanup plan/approval: run-owned KB before exclusive owned dependencies.
Keep reused resources, source content, retained sources' children/shared roles.
`operation: delete`: owned digest/fresh ETag; unclear ownership blocks.

## Return contract

Return status/IDs/API/mode/model, access/data movement, verification,
first failure/warnings/ownership/cleanup; hide digests.

## References

- [Audit fields](../references/platform-contracts.md).
- [Interface versions](../references/platform-interfaces.md).

Authorities: failure/conflict/uncertainty only.

- [Preview](https://learn.microsoft.com/rest/api/searchservice/knowledge-bases/create-or-update?view=rest-searchservice-2026-08-01-preview)
- [Reasoning/models](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-set-retrieval-reasoning-effort)
