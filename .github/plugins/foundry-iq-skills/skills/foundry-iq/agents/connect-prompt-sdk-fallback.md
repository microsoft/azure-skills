# Existing Prompt Agent SDK fallback

Use this fallback only when authenticated Foundry MCP is unavailable
or lacks connection/version operations, never denial/conflict.
Select before planning; require the parent's approved child fingerprint before ARM creation;
do not read policy unless a creation failure implicates it. Unsupported settings block.
Read `helpers/contracts.md`; verify SDK/CLI identity. Install only missing/incompatible dependencies after approval:

```text
python -m pip install --pre "azure-ai-projects>=2.4.0,<3" "azure-identity>=1.25.0,<2"
```

Run `az login` only if unauthenticated. ARM uses signed-in CLI identity;
SDK and shared cleanup loader use `AzureCliCredential`, not environment/MI fallback.
Missing CLI authentication blocks noninteractively, never falls back to another identity.
Keep CLI context unchanged; never silently switch tenant/identity.
SDK errors: safe code/HTTP status/server ID (`x-ms-request-id`, then `request-id`).
Client request IDs are not server provenance; raw exception text is withheld.
Ambiguous creation stays partial with original status/ID even if recovery fails.
Observed matching versions do not prove creation ownership. CLI output separates
`resources_remaining.unverified` from run-owned resources; unknown versions remain unnamed.
`request.json` (resolved intent, not hand-built bodies/hashes):

```json
{
  "schema_version": "1.0",
  "project_resource_id": "<exact project ARM ID>",
  "project_endpoint": "https://account.services.ai.azure.com/api/projects/project",
  "search_resource_id": "<exact Search ARM ID>",
  "knowledge_base_name": "kb",
  "agent_name": "agent",
  "agent_version": "1",
  "connection_name": "kb-project-mi",
  "is_shared_to_all": false,
  "binding_action": "ensure",
  "role_assignment_id": "<Search ID>/providers/Microsoft.Authorization/roleAssignments/<GUID>",
  "permission_forwarding": {"mode": "not-applicable"},
  "network": {"posture": "public", "evidence": "<verified reachability>"},
  "owner": "<owner>"
}
```

```text
python helpers/prompt_connect.py --plan request.json
```

Use observed choices, never latest. Output: `status: planned`, `approval_summary`,
`execution_input`, `approval.confirmed: false`; no writes/installation/inference.
Read CLI context, exact project/KB/role/connection, selected version and all scoped
version pages including drafts; no account/index/connection enumeration.
Bounds: 1 MiB input/readback/definition, 200 KB sources, 200 agent versions/pages.
At 200 versions, new-version apply/plan blocks before writes; exact reuse remains valid.
Unresolved KB profiles block, never transition the KB. Verify the PROJECT principal's
exact Search Index Data Reader grant; missing roles block, never assign.
Search provisioning/degraded warns only with healthy KB GET;
failed/deleting/disabled or unavailable reads block.

Review names, binding/grounding delta, sharing, principal/scope and preserved state.
Save `execution_input` privately; after consent set `approval.confirmed` true,
without changing plan or fingerprint. Fresh exact reuse:
`execution_required: false`, `mutation_approval_required: false`; stop without approval/apply.
Otherwise:

```text
python helpers/prompt_connect.py --input <approved-envelope.json>
```

Bind project ID/endpoint, agent/version/model/digest, absent/exact ARM connection,
KB MCP endpoint, `allowed_tools: ["knowledge_base_retrieve"]`, `require_approval: "never"`,
role ID/principal/scope, permission forwarding, owner, `cleanup_approved: false`.
`grounding_instructions` binds the exact appended evidence-only text;
old envelopes cannot authorize grounding upgrades.

```text
For every user question, call knowledge_base_retrieve before answering, including questions that seem unrelated to the knowledge base. Answer only from evidence returned for that question and cite the original sources. Do not answer from general knowledge or assume an answer without retrieval. If the retrieved evidence does not support an answer, reply exactly: I don't know. Do not add citations to an unsupported answer. If retrieval fails, report the failure instead of treating it as no evidence or answering from general knowledge.
```

Model/type/connection conflicts and duplicate same-label MCP tools block. Same-label MCP tool drift
requires `binding_action: replace-selected`; inline auth/connectors/conflicting headers
still block. Preserve definition/metadata/description/draft/blueprint reference.
Reuse the sole exact version without `create_version`, or create at most one ARM
connection and one same-agent version via `project.agents.create_version`; read both back.
Normalize only selected MCP `allowed_tools` list versus `tool_names` object encoding
(including `read_only: null`); other fields stay strict, including unrelated tools.
Use that comparison for reuse/recovery/verification, but approval/ownership hashes
bind original readback. Same-name non-equivalent connections conflict even with legacy
`update`; choose a new name, retain legacy/key connections on the same KB endpoint.
Legacy schema/hashes unchanged. Refresh version inventory/prerequisites before writes;
portal changes invalidate plans. Replan after execution; snapshots are not concurrency locks.
Permission forwarding: not applicable or named `search_auth_token` structured input,
value per request only. Exit `2`: no-write blocked; `3`: partial/ambiguous, never success.

Use `Microsoft.CognitiveServices/accounts/projects/connections`.
Disclose `connection.is_shared_to_all` (default `true`) and actual sharing.
Server type metadata or boolean true→false restriction differences warn, not rewrite.
Missing/malformed sharing, broadened access, identity/target/auth/audience/category/
required-metadata mismatches block; explicit false rejects nonempty `sharedUserList`.
Preserve warnings after agent failure; compare creation, ambiguous-write recovery and reuse
consistently. `completed` verifies configuration only; actual
invocation/citations/unsupported-question checks remain required.

Connection approval excludes cleanup; use the separate cleanup planner.
After separate approval, invoke:

```text
python helpers/prompt_cleanup.py --input <approved-cleanup-envelope.json>
```

Cleanup binds run-owned identities, digests and connection ETag; deletes version before
connection; verifies absence including drafts. Preserve prior versions/project/model/KB/roles.

## Creation receipts

Before create:
`--cleanup-receipt-dir "<absolute-existing-private-directory>"` to approved
`--input`; keep `cleanup_receipts` and original input.
Only `verified` receipts seed [separate cleanup](../lifecycle/cleanup.md);
`acknowledged`/reuse/update/recovery are not ownership proof.
Store native IDs/hashes/versions, never credentials/bodies.

### Initial Prompt creation only

Verify project/model/identity/network prerequisites before local initial creation.
`python helpers/prompt_connect.py --plan-initial <request.json>`.
Closed request: `schema_version: "1.0"`, `owner`, `project_resource_id`, `project_endpoint`,
`agent: {name, definition}`, `prerequisites` evidence strings keyed by
`project`, `model`, `identity`, `network`; optional `inventory_limits`:
integer `max_pages`/`max_resources` (default 20/500, max 100/5000).
Closed definition: `kind: "prompt"`, verified deployment `model`, `instructions`, `tools: []`.
Evidence descriptions are not platform verification.

Review `execution_input`; change only `approval.confirmed`.
Apply `--input <approved.json>` with receipt flag:
Foundry v1 `POST <project-endpoint>/agents?api-version=v1`, never create-version on replay.
Complete project inventory/exact GET prove absence; existing names, changes,
denied/partial reads or ambiguous writes block. No POST retry.
HTTP 200 `AgentObject.versions.latest` plus independent version GET bind the receipt.
Post-ACK failure is partial, not ownership recovery. No invocation/provisioning/grants/
Hosted creation. Cleanup retains container and other versions.
