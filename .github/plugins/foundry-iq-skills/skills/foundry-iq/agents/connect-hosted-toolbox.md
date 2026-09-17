# Hosted toolbox-only connection

For an existing unversioned toolbox consumer, changing the default needs no source,
`azure.yaml`, environment setter or deployment. Preserve the observed agent version/definition.

**Execution limit:** service version creation/promotion exists; this helper is
GET-only. Conditional ETag/default-update enforcement is unverified. Changed bindings
return `toolbox-promotion-concurrency-unverified` before connection/version creation.
No arbitrary PATCH headers or unconditional `azd ai toolbox publish` bypass.
Obtain the service owner's conditional-update contract, not Hosted source.

Disclose upfront: the owner is the **retained connection/toolbox-version owner**.
Hosted cleanup is unsupported. Retain prior immutable versions and legacy
connections; rollback needs its own explicit plan/approval, never automatic action.

## Resolve and inspect

Accept project/KB names, resource IDs or endpoints. Exact selections win.
Resolve missing parents only within selected subscription/RG/account.
Ambiguity returns `selection_candidates`; denied/malformed pages block, never widen scope.
Search index lists never prove KB identity or absence.

Four layers: **project connection** authenticates KB MCP; **toolbox** holds the default;
**immutable toolbox version** references connections; **Hosted runtime binding** consumes
the endpoint. The KB stays unchanged in Search.

This recipe requires `RemoteTool` + `AgenticIdentityToken` + Search audience
`https://search.azure.com/` + exact KB MCP endpoint. `CustomKeys` and
`ProjectManagedIdentity` are not interchangeable here; other authorized custom
Hosted runtimes may support those auth modes. Preserve legacy names.
Collide by connection NAME, not endpoint. New explicit names may share a KB endpoint;
never overwrite mismatches or retry random names. Opaque tool auth/headers block;
preserve tool approval/filter policies.

The access principal is the active published Hosted agent's `instance_identity.principal_id`,
not the blueprint or project principal used by the Prompt `ProjectManagedIdentity`
recipe. Verify existing Search Index Data Reader at the Search service and Foundry
User at the project. The helper checks these exact built-in grants; equivalent
custom grants need separate authoritative verification, not broader assignments.

The consumer endpoint is `<project-endpoint>/toolboxes/<name>/mcp?api-version=v1`.
`/toolboxes/<name>/versions/<version>/mcp` is a pinned developer endpoint, not
equivalent. A mismatched endpoint/environment requires explaining the actual
runtime/config/deploy change and then handing off/requesting source if needed.
FoundryToolbox prefers present `TOOLBOX_ENDPOINT` (empty is invalid); only when absent does it combine
`FOUNDRY_PROJECT_ENDPOINT` (trailing slash removed) and `TOOLBOX_NAME`.
Explicit endpoint wins over name/project settings; pinned or mismatched results block.
These are supported configuration conventions, not proof arbitrary code uses them:
a constructor URL overrides the resolver. Runtime usage stays unverified until actual acceptance.

## GET-only assessment

Save semantic choices as `intent.json`:

```json
{
  "schema_version": "1.0",
  "scope": {"subscription_id": "<selected-sub>", "resource_group": "<selected-rg>", "account_name": "<known-account>"},
  "project": "<project-name-or-ID-or-endpoint>",
  "search_service": "<service-name-or-ID-or-endpoint>",
  "knowledge_base": "<KB-name-or-preview-MCP-endpoint>",
  "agent_name": "<observed-agent>",
  "agent_version": "<observed-version>",
  "toolbox_name": "<existing-toolbox>",
  "tool_label": "<observed-selected-MCP-label>",
  "connection_name": "<explicit-agentic-connection-name>",
  "reader_assignment_id": "<Search-ID>/providers/Microsoft.Authorization/roleAssignments/<GUID>",
  "project_assignment_id": "<project-ID>/providers/Microsoft.Authorization/roleAssignments/<GUID>",
  "retention_owner": "<owner>"
}
```

```text
python helpers/hosted_connect.py --plan intent.json
```

Omit `account_name` only when scoped account/project discovery is needed.
Optional `known_agents: [{"name":"...","version":"..."}]` adds up to 20 known
binding readbacks, not an account-wide consumer scan. Limits: 1 MiB input/REST
responses; 20 pages/100 items per scoped inventory; at most 20 accounts and 200 tools.

Output: `approval_summary`, private fingerprint, request IDs, zero writes.
Exact configured reuse is `planned`, without mutation approval.
Changed state is `blocked`; `execution_input` is null and `execution_available` is false;
no consent/apply mode. Fresh agent/default/version/connection or CLI-context drift blocks.

Present this compact delta, not integrity hashes:

| Item | Before | Proposed after |
|---|---|---|
| KB tool binding | Observed endpoint/connection | Selected endpoint/new compatible name |
| Toolbox default | Observed immutable version | New immutable version; ID not yet created |
| Agent | Exact observed version/runtime | **UNCHANGED** |

## Shared-default approval and future write gate

Promotion affects **every consumer** following the default, including external
clients. Show known bindings and unknown scope; never infer exclusive ownership
from a selected-agent read or partial inventory. Require explicit approval of this
shared-default effect plus the precise binding/auth/tool delta and retention.

SDK 2.4 `project.toolboxes` exposes `get(name)`, `get_version(name, version)`,
`create_version(name, tools=...)`, `update(name, default_version=...)`.
REST `v1` uses GET `/toolboxes/<name>` and `/toolboxes/<name>/versions/<version>`,
POST `/toolboxes/<name>/versions`, then PATCH `/toolboxes/<name>` with
`{"default_version":"<created-version>"}`. These are service capabilities,
**not executable approval through this helper**.

Future writes require conditional promotion semantics, fresh default/ETag/protected state,
conflict blocking and preservation of unrelated tools/skills/metadata/policies.
The first toolbox version becomes default automatically; never create it accidentally.
Verify connection/version before promotion, then default and unchanged agent binding.
Partial failures retain original errors/ownership; no automatic rollback or cleanup.

## Acceptance and portal help

If no known-answer question is supplied, first reuse authorized retrieval evidence for this KB.
Otherwise the workflow owner may perform bounded KB retrieval only within an
approved data/model-cost boundary, then propose an evidence-backed question for
customer approval. Read-only retrieval may invoke embedding/chat and incur cost.
Do not fabricate payloads, add a probe when evidence is already known, or query
during this GET-only assessment. Optional `supported_question` and
`unrelated_question` are candidates, not invocation consent. Require a separate
unrelated abstention question and approval.

Acceptance requires the actual selected agent's `knowledge_base_retrieve` activity,
original-source citations and unsupported-question abstention, not merely KB REST.
Pin its version, keep requested sessions/conversations and usage distinct, and
leave unavailable runtime/tool payload evidence unverified.

UI help is optional, never a setup gate. Current first-party guidance:
**Manage > Project details > Connected resources**; older layouts/user screenshots
may say **Management center > Connected resources**. For the reported portal layout,
look under **Build > Tools > Toolboxes**; labels vary and this path is not API evidence.
Authorities: failure/conflict/uncertainty only.

- [FoundryToolbox resolver](https://github.com/microsoft/agent-framework/blob/main/python/packages/foundry_hosting/agent_framework_foundry_hosting/_toolbox.py)
- [Toolbox operations and endpoints](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)
- [Connection UI](https://learn.microsoft.com/azure/foundry/how-to/connections-add)
- [Hosted code ownership](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)
