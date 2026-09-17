# Knowledge-base planning contract

Use for KB creation/reuse or the explicit model-free agent transition.
The [KB owner](../knowledge-bases/create.md) resolves goals, source readiness,
access and costs; [common contracts](contracts.md) govern approval and execution.
No helper source inspection, hand-built `desired`/models or hash scripts on the
normal path. Reuse supplied choices instead of asking another questionnaire.

## Read-only planning

```text
python helpers/search_reconcile.py --plan <kb-intent.json>
```

Closed UTF-8 input, at most one MiB:

```json
{"schema_version":"1.0","endpoint":"https://svc.search.windows.net","name":"docs-kb","owner":"operator@example.com","source_name":"docs-file","api_version":"2026-08-01-preview","reasoning_effort":"minimal","output_mode":"extractiveData"}
```

All shown fields are required. `name`/`source_name` are exact names, not patterns;
owner is workflow metadata, not wire data. Names are URL-encoded, never code.
`action` defaults to `create-or-reuse`. Renaming after collision needs approval.

| Choice | Supported shape |
|---|---|
| API | `2026-04-01` for Blob minimal/extractive; `2026-08-01-preview` for File/ADLS, reasoning/synthesis or agents |
| Reasoning/output | Preview `minimal`/`low`/`medium`: `extractiveData` or `answerSynthesis`; GA minimal/extractive only |
| Model | Omit/null for minimal/extractive; one explicit `model` below for low/medium or synthesis |
| Optional text | `description`, `retrieval_instructions`, `answer_instructions`: text/null, each at most 4096 characters; instructions preview-only |
| Optional controls | Existing closed `data_movement`, `rbac`, `network` objects from common contracts |

No implicit API/mode/model choice, escalation or CU/vector inference. Source
processing and embeddings remain unchanged. Unknown fields and invalid choices
block before authentication. No keys, secret environments, model provisioning,
network/RBAC changes or model calls.

### Reasoning or synthesis with a chat model

Use resolved deployment/model choices, not guesses or a hardcoded default:

```json
{"schema_version":"1.0","endpoint":"https://svc.search.windows.net","name":"docs-kb-synthesis","owner":"operator@example.com","source_name":"docs-file","api_version":"2026-08-01-preview","reasoning_effort":"low","output_mode":"answerSynthesis","model":{"endpoint":"https://models.services.ai.azure.com","deployment":"chat-deployment","model":"gpt-4.1-mini","auth":"system-assigned","prerequisites":{"deployment":"<verified deployment/model reference>","identity":"<verified Search identity/role reference>","network":"<verified reachability reference>"}}}
```

`model` accepts only those five fields. Prerequisites are nonempty text, at most
4096 characters each: owner attestations, not helper proof of capacity/readiness/access.
Use a supported Azure OpenAI chat model, exact public-cloud account endpoint and deployment.
The Search system identity needs model access. CU/embeddings are not KB chat.
For medium or minimal synthesis, change `reasoning_effort` accordingly; retain
the model. Minimal synthesis adds model cost without query planning; use `intents`,
not `messages`, for retrieval. Never auto-escalate or change extractive defaults.

The helper generates the complete wire definition, including:

```json
{"name":"docs-kb-synthesis","knowledgeSources":[{"name":"docs-file"}],"retrievalReasoningEffort":{"kind":"low"},"outputMode":"answerSynthesis","models":[{"kind":"azureOpenAI","azureOpenAIParameters":{"resourceUri":"https://models.services.ai.azure.com","deploymentId":"chat-deployment","modelName":"gpt-4.1-mini","authIdentity":null}}]}
```

No `apiKey`. Only minimal/extractive omits models. GA omits preview fields/models.
New artifacts bind
`kb_plan_version: "1.0"` and `kb_model` (null or the selected choice) to that wire
definition. Existing approved artifacts retain their fingerprints; preview
minimal/synthesis is now admitted with one model.
Masked/nonempty keys or a different model identity in KB readback block; they
cannot be hidden by generic definition normalization.

## Observation, result and approval

Only selected Search `GET knowledgesources('{source}')` and
`GET knowledgebases('{name}')`, using the requested API and signed-in CLI token.
Source GETs bracket KB observation; existing KBs are reread for ETag/definition
stability. Three GETs for an absent KB, four for existing; no resource enumeration,
status polling, uploads, retrieval, PUT/PATCH/DELETE or writes to local artifacts.
These observations are not locks or ingestion/retrieval proof.

The source must exist and return the exact selected File/Blob/ADLS definition.
The helper derives `verified_source` name/normalized definition digest from
those reads; never supply or fabricate it in the intent. Finish source-owner
readiness and prerequisite verification before mutation approval.

Exit `0`: `status: planned`, `execution_input`, `plan_fingerprint`,
`approval_summary`, read request IDs and `writes_performed: []`.
Save only `execution_input` in a private UTF-8 JSON file. It already contains
the complete plan and computed fingerprint, with `approval.confirmed: false`.
Do not wrap it again, edit its generated body or calculate a fingerprint.
Summaries omit prerequisite references; retain private artifact data privately.

An exact existing KB is observed reuse, not a prediction: stable name/definition/
ETag, `action: reuse`, `execution_required: false`,
`mutation_approval_required: false`. Do not execute an unapproved envelope just
to repeat this read-only verification. Continue authorized retrieval; ingestion
and retrieval remain explicitly unverified by planning.

Otherwise present concrete actions/source/mode/model, access, cost/data movement,
acceptance and cleanup. An already-confirmed concrete plan is not a reason to
repeat choice questions; confirm any material difference before proceeding.
Only actual approval of the unchanged generated plan permits setting its existing
`approval.confirmed` to true; preserve the supplied fingerprint. Tool permission,
bootstrap consent or a proposed future source does not establish that approval.
The planner never infers consent from the input.

```text
python helpers/search_reconcile.py --input <approved-envelope.json>
```

Apply freshly verifies the source binding, conditional create or current ETag
update, exact readback and keyless model auth. Source/KB drift blocks; regenerate
the proposal and review changes, never hand-repair nested JSON/hashes.
Exit `2` is structured blocked/no-write; post-write failures are `3`/partial
with retained ownership. No automatic retries of writes or cleanup.
An updated KB remains pre-existing/reused, including failed or ambiguous
post-write verification; an update never establishes creation ownership.

## Explicit agent-minimal transition

This is optional KB-side model-free normalization, not an MCP prerequisite.
Never downgrade a valid reasoning/synthesis KB to connect an agent.
For the owner's existing model-free GA/extractive KB transition, set
`action: agent-minimal-transition`, preview API, minimal effort and extractive
output. Omit model and optional text changes. The source/KB must exist and match.
Existing absent/minimal/low effort is allowed only without models and synthesis;
the summary discloses prior mode fields, including an observed default low.
Only the two preview mode fields change, guarded by the current ETag; unrelated
fields/models remain. The update needs separate concrete approval.
An equivalent KB is reuse. Verify actual agent MCP invocation separately from GA REST retrieval.

## Authorities

Authorities: failure/conflict/uncertainty only.
[preview KB wire/model fields](https://learn.microsoft.com/rest/api/searchservice/knowledge-bases/create-or-update?view=rest-searchservice-2026-08-01-preview),
[KB creation and model access](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base).
