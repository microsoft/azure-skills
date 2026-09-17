# Retrieve from a knowledge base

## When to use

One KB query; opt-in offline/agent audits.

## Do not use

No creation/repair/sync/connection/RBAC/effort changes or cleanup.
Failures/drift: [Diagnose](../troubleshooting/diagnose.md). Never return credentials.

## Inputs and discovery order

Standalone: Search REST retrieve with Entra auth, no MCP/agent required.
Check CLI/sign-in; preserve `azure-authentication-failed` or `azure-cli-unavailable`.
Never install/switch identity implicitly. Capture privately:
`az account show --output json`; for a user,
`az ad signed-in-user show --query id --output tsv` (no subscription flag).

Never request tokens/credentials/keys in chat.
Missing verified host auth blocks; pasted tokens aren't a remedy.

Resolve prompt/session/workspace/exact Azure readback; one focused question. Label evidence.
Discovery needs no approval; run only authorized queries. Retrieval can invoke
models/cost/data movement. Silence never selects identity/permissions/extra queries.

| Input | Why needed | Required? | Discovery order | Safe default | If missing or unanswered | Reconfirmation trigger |
|---|---|---|---|---|---|---|
| Search/base ID/endpoint | Target | Yes | Prompt/session/GET | None | Ask ambiguity | No writes |
| API/definition/mode | Shape | Yes | Creation/GET | None | Ask/block | None |
| Query | Retrieval | Yes | Prompt | None | Ask | None |
| Caller | Access | Yes | Identity GET | None | Block | None |
| Forwarding | Access | If needed | Source/base GET | None | Block | None |
| Original identity | Citations | Opt-in audit | Inventory | None | Unverifiable | None |
| Unrelated question | Abstention | Opt-in audit | Authorized evidence | None | Not tested | None |
| Agent/tool identity | Tool proof | Audit | GET | None | Block | None |

## Decisions

GET base/source definitions; connection binding is not definition evidence.
Use the API from creation evidence or ask before GET; it isn't a returned field.
GA `2026-04-01` is extractive. Preview minimal can synthesize with a configured
KB chat model; still use `intents`. Preserve observed output/effort.

KB/model changes: [KB setup](create.md) selects chat model and separately approved
deployment/configuration. No retrieval-time mutation or fallback to minimal.

Inspect source `ingestionPermissionOptions` in ingestion parameters; unknown
posture blocks. Permission-enabled retrieval requires per-request
`x-ms-query-source-authorization`, audience `https://search.azure.com/.default`,
separate from service auth. Forward only the verified same signed-in user's
token; otherwise `permission-forwarding-unavailable`. Never persist/log tokens;
do not pass the caller token as a CLI argument. Never query unfiltered as fallback.

## Proposed plan

State target/API/mode, caller/query/forwarding, citation identity and optional
audit; `mutation: none`.

## Confirmation

No mutation approval gate. Confirm acceptance questions not already authorized;
do not auto-run queries. Writes need the owner's separate plan and confirmation.

## Mutation

None; never retry through another resource.

Standalone: use selected endpoint/name/API and observed effort. Query is JSON
data, never shell text. GA/preview minimal use `intents`; preview low/medium uses
`messages`. Never override mode/effort/models/source selection.

Invoke by loaded skill path, not customer project; never read/copy source or replace:

```text
python "<skill-dir>/helpers/knowledge_base_retrieve.py" --input "<request.json>"
```

Definition GET, UTF-8 JSON:

```json
{"operation":"get-knowledge-base","endpoint":"https://<service>.search.windows.net","name":"<kb>","api_version":"2026-08-01-preview"}
```

Read selected sources with `operation: get-knowledge-source` and exact name.
Helper escapes OData; do not pre-encode. Inspect definitions/permissions; use
observed effort and explicit forwarding:

```json
{"operation":"retrieve","endpoint":"https://<service>.search.windows.net","name":"<kb>","api_version":"2026-08-01-preview","effort":"minimal","query":"<question>","forward_permissions":false}
```

Use the selected API. Closed inputs: no approval envelope/fingerprint/credentials.
Set `forward_permissions: true` only for the verified same signed-in user when
the source requires forwarding. The helper additionally checks CLI user type,
then acquires the token in memory. It never accepts a caller token as input.

Helper retains HTTP status/request ID, disables redirects, bounds bytes, never retries.
Exit `0`: `status: response-received`, `http_status`, `request_id`, `response_body`;
not grounding/end-to-end proof. Exit `2`: `status: blocked`, first code/status/request ID,
no writes/ownership/cleanup, even for ambiguous POST. No tokens/raw diagnostics.

REST results contain `response`, `references`, and optional `activity`; they are
not MCP `result.content[]`. Parse all returned text blocks and reference IDs.
Activity errors or missing grounding are incomplete, not success. HTTP `206`
is rejected even with valid-looking content. No-support is valid; never fill
gaps from general knowledge.

Requested agent audits: invoke supported host; verify native per-KB
`knowledge_base_retrieve` call. Missing connection:
`knowledge-base-mcp-endpoint-unavailable`; do not substitute REST as agent proof.
Never substitute a generic index query or the generic Azure MCP Server
`search_*` tool group for either path.

## Verification

For ordinary retrieval, check the requested answer, native references and activity;
missing grounding/errors remain incomplete. No extra questions or retained bundle.

Offline audit is **opt-in**; default `audit_status: not-requested`.
No hand-authored Q&A required. Propose title/content questions only from authorized
content, not structural assessment. Approve proposed queries before execution;
never derive ground truth from audited answers. No samples/questions: defer audit.
After opt-in, follow the paired
[audit contract](../helpers/retrieval-verification-contracts.md):
`python "<skill-dir>/helpers/retrieval_verify.py" --input "<private-bundle>/audit.json"`.
No custom parsing/raw dumps/reretrieval; exit `0` isn't acceptance. Skipping is not a pass.

Audit original File path plus file ID or Blob/ADLS URL/path plus ETag/version;
native `docName`/`blobUrl` lack File ID/ETag: report unverified, not chunk-ID proof.
For synthesis audits, apply the shared
[semantic abstention criteria](../references/abstention.md),
honoring any explicit exact-output contract.
GA/preview extractive audits require no supporting extracts: do not invent a
synthesized `I don't know`. Structural absence isn't semantic abstention.
Recheck identities; require
`before_after_snapshot_equal: true`.

## Failure and partial completion

Denial is inaccessible, not absence. Diagnose empty/wrong/stale output without
mutation. No fabricated citations/success; failures create no ownership.

## Cleanup

Not applicable. No resources or cleanup approval.

## Return contract

Verified: `status: completed`, `outcome: knowledge-base-retrieval`,
`mutation: none`, KB/source IDs/endpoint/API/mode, `preview: true|false`,
caller/forwarding, requested answer/citations, activity/tool evidence, warnings/latency,
`audit_status`, abstention tested/evidence and before/after equality when audited.
Otherwise return `status: blocked`, `blocked_at`, first status/message/request ID,
missing/conflicting input, safe next decision, `writes_performed: []`, no new
ownership and `cleanup: not-applicable`. Never report unavailable evidence as
verified or include credentials/raw diagnostics.

## References

- [Abstention criteria](../references/abstention.md): required for synthesis audits.
- Optional [audit schema](../references/platform-contracts.md) and
  [versions](../references/platform-interfaces.md); not required normal-path reads.

Authorities: failure/conflict/uncertainty only.

- [Retrieve using a knowledge base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)
