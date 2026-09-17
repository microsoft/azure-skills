# Intent, handoffs and completion examples

Read for ambiguous/compound goals, unresolved search-mode choices, or uncertainty
about completion. These examples guide interpretation, not keyword-first matching.

## Intent and completion

Route by the user's end result, not the first connector/resource keyword.
Within Foundry IQ, "make these documents searchable" or "ask questions over these
documents" means a usable KB with validated retrieval. Default to Create KB,
not a source-only operation. Words such as files, Blob, index or embeddings
identify prerequisites; they do not downscope a broader goal.

Confirm the intended finish once in normal intake, in user terms: "I'll make
these documents searchable through a knowledge base and check retrieval against
them. Do you want that full outcome, or only the knowledge source?"
Do not re-ask an already explicit or confirmed goal. Use source-only only when
the user explicitly requests or confirms that narrower outcome; never infer it
from an intermediate step. Goal confirmation is not approval for Azure writes.

Retain the confirmed goal, selected data, explicit exclusions and remaining steps
across handoffs. A child's `completed` result is not overall completion.
For a KB goal, resume the KB owner after Search/model/source prerequisites with
returned IDs and fresh source/readiness evidence. Present and approve the concrete
KB plan, create/reuse and read back the KB, then run supported-question and
unrelated-question retrieval checks under the selected API/output mode.
Require source-backed results and original-source citations; source ingestion,
KB existence or HTTP success alone is not validated retrieval.

Finish only when every requested outcome is verified. Otherwise report completed
prerequisites, the blocker and remaining steps; never mark the whole goal complete
or silently downgrade it to KS-only. Resume after an approved prerequisite rather
than asking the user to restart. Never preapprove an unknown KB mutation.
Explicit source-only, infrastructure-only and read-only requests remain bounded;
never create an unrequested KB/agent. Explicit classic Search work still routes out.

## Search-mode choice

For **new unresolved search-mode intent**, recommend/preselect **Hybrid
(keyword + vector)**, with **Keyword-only (disable vectors)** as the explicit
opt-out. This recommendation is not consent or a helper default.
Honor existing/informed keyword-only choices and exact reuse unchanged: do not
re-ask settled choices, silently retrofit vectors or choose/deploy a model.
An explicit change to an existing source needs a separate supported plan/approval;
read-only retrieval never changes its source.

Ask in the grouped intake: "I recommend Hybrid (keyword + vector) for keyword
precision plus semantic/paraphrase matching. Would you like Hybrid, or Keyword-only
without vectors?" Where selectable defaults are supported, preselect Hybrid, but
require an explicit customer choice; silence or an unanswered field is not consent.
Reuse supplied informed choices and group compatible unresolved decisions rather
than adding separate confirmations for each disclosure.

Before plan approval explain:

| Choice | Benefit and tradeoff |
|---|---|
| Hybrid (recommended) | Combines keyword precision with semantic/paraphrase matching, including related wording without exact terms. Adds embedding charges, ingestion/query embedding processing where applicable, vector storage/capacity, and content processing/data movement to the selected embedding service. Disclose selected model, region, auth/network and applicable cost/data boundaries; no guaranteed relevance improvement. |
| Keyword-only (opt-out) | Keeps keyword matching without source vectors or their embedding charges/processing/storage. May miss paraphrases with little term overlap. Search, extraction and independently requested chat/CU can still cost money; this is not a free or model-free promise. |

Keyword-only: no embedding discovery. Discover only missing dependencies for the
confirmed hybrid choice, using the bounded scoped helper; select an account before
listing its deployments. Known compatible model choices need exact readback, not
rediscovery. Never auto-select a deployment, deploy models, call models or upload
content during intake. Missing/unavailable hybrid dependencies require supported
scoped discovery, concretely approved setup, or explicit customer keyword-only
opt-out; no silent keyword fallback. Report readback/access/capacity uncertainty
precisely; metadata is candidate evidence, not effective readiness.
Model-free minimal+extractive routes do zero model/CU discovery; keyword-only does
not suppress independently required chat/CU discovery.

Retrieval keyword+vector is independent of text-only versus multimodal extraction.
Neither search choice selects CU, KB reasoning/synthesis or semantic reranker
automatically. A text-only PDF can use hybrid; multimodal content can use
keyword-only. Assess extraction/answer dependence separately without defaulting
Minimal or selecting Standard merely because an image/table exists.

Keep helper inputs explicit: File `vectorization: none` versus `azureOpenAI`;
Blob `minimal-lexical` versus `minimal-vector`, or `standard-cu` with independently
selected optional embeddings. File/Blob JSON examples are explicit keyword-only
choices, not UX defaults. Omitted/null embeddings never become vectors; a selected
vector mode with missing model choices blocks, not downgrades. Preserve separate
sample-content consent and actual resource/permission/CU/source/KB approvals;
do not approve unknown future bodies. Approved source creation/ingestion is not
validated hybrid retrieval; use the existing vector/hybrid verification contract
with explicit query approval, not a billable intake probe.

## Scenario examples

Read the whole request; broader goals and explicit limits take precedence over a
mentioned child step.

| User request | Start | Required finish |
|---|---|---|
| Make these local documents searchable. | [Create KB](../knowledge-bases/create.md) | Confirm KB outcome; File prerequisite, valid KB and validated retrieval. |
| Make this Blob container searchable. | [Create KB](../knowledge-bases/create.md) | Confirm KB outcome; Blob prerequisite, valid KB and validated retrieval. |
| Create a Blob knowledge source, then a knowledge base and test it. | [Create KB](../knowledge-bases/create.md) | Both resources and validated retrieval; do not stop at the KS. |
| Use my existing Search service to make these files searchable. | [Create KB](../knowledge-bases/create.md) | Reuse Search; finish the KB and retrieval, not just infrastructure. |
| Create only a Blob knowledge source; no KB. | [Blob family](../knowledge-sources/create-azure-blob.md) | Verified source only; no KB or agent creation. |
| Set up only a Search service. | [Search](../search-services/create.md) | Verified service only; no source or KB creation. |
| Query this existing KB. | [Retrieve](../knowledge-bases/retrieve.md) | Read-only source-backed retrieval; no creation. |
| Connect this KB to my existing Foundry agent. | [Connect](../agents/connect.md) | Verified requested connection and agent retrieval; configuration alone is insufficient. |
| Make OneLake and Blob searchable together. | [Diagnose](../troubleshooting/diagnose.md) | Explain unsupported scope; never substitute a Blob-only success. |
| Build a classic Search index and query it from my app. | Outside this skill | Classic Search handoff; do not invent a KB requirement. |

## References

Authorities: failure/conflict/uncertainty only.

- [Hybrid search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview)
- [Integrated ingestion/query vectorization](https://learn.microsoft.com/en-us/azure/search/vector-search-integrated-vectorization)
