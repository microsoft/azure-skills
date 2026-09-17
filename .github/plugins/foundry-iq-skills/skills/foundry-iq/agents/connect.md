# Connect a knowledge base to an agent

## When to use

Connect one Prompt/Hosted Agent; optionally create it if missing.
KB: content; project connection: auth; agent MCP tool: versioned use.

## Do not use

Do not replace agents, attach multiple base tools, or handle base-free lifecycle.
Permission error is not absence; creation approval is separate.

## Inputs and discovery order

Resolve prompt, session, workspace, exact Azure readback, default, then one focused question.
Label sources; missing input blocks. Reads need no approval; silence approves nothing.

| Input | Why needed | Required? | Discovery order | Safe default | If missing or unanswered | Reconfirmation trigger |
|---|---|---|---|---|---|---|
| Base return/MCP endpoint | Grounding | Required | Session, exact proof | None | Block | Base/API/evidence change |
| Project ID/endpoint | Target | Required | Prompt, workspace, readback | None | Block | ID/tenant change |
| Agent name/inventory/type | Identity | Required | Prompt, readback | Never latest/type | Block ambiguity | Inventory/type |
| Definition/model/baseline; Hosted telemetry | Preservation | By branch | Exact readback | Preserve unrelated fields | Block | Protected state |
| Connection/tool; Hosted toolbox/environment | Binding | By branch | Full readback | One retrieve binding | Block conflict | Binding/endpoint |
| Principal/reader role | Retrieval | Before assignment | Readback | Exact Search scope | Block | Assignment |
| Grounding delta | Evidence | Required | Instructions | Base/citations/`I don't know` | Block loss | Delta |
| Acceptance/unrelated questions | Verification | Before invocation | Authorized evidence | None | Propose candidate | Questions |
| Cleanup/retention owner | Ownership | Required | Prompt/session | None | Block | Owner |
| Provider/install or CLI choice | Missing agent | Conditional | Runtime, then choice | No automatic fallback | Block | Availability/choice |

## Decisions

Use [policy diagnostics](../references/search-substrate.md#azure-policy-diagnostics-after-creation-failure)
only after a creation failure implicates policy, never as a gate.

Read exact IDs/all scoped pages; inaccessible is not absent:

- **Prompt:** refresh the selected version and all its scoped version pages after
  portal add/remove; never assume latest. Exact is zero-write. Collision is the
  connection NAME, not KB endpoint: an approved new name can share that endpoint,
  preserving legacy/key connections. Same-name mismatch blocks. An explicit
  selected-tool switch creates a version, preserving all unrelated fields/tools.
- **Hosted:** inspect remote project, exact agent/version, KB MCP, runtime principal
  and connection/toolbox/binding first: no source path for inspection or exact reuse.
  Bind source/config digest for agent edits/redeployment.
  Conflicts block. Read [Hosted connection](connect-hosted.md)
  before plans or verification.

Only for a missing agent, load [missing-agent creation](create-missing-agent.md)
before questions/plans. Prefer `microsoft-foundry`: delegate approved
identity/configuration and known requirements. Otherwise offer installation
or Prompt CLI creation. Installation refusal is not creation approval.
Require a typed return with project, agent, version/deployment, model/status/identity
and definition/source/config/environment. Independently read back;
use fresh discovery and a new fingerprinted connection plan;
never carry creation approval. Incomplete returns block.

Read the authenticated `knowledgebases` API, never generated indexes
or `foundryextensions_knowledge_index_list`. Existing multi-source KBs are valid.
Preserve valid KB effort/output/models; preview MCP supports reasoning/synthesis.
Use the exact preview API in SDK; native GA minimal/extractive MCP exists.
KB model: low or medium with supported output; preview minimal/answerSynthesis is valid.
Use the approved [KB transition](../knowledge-bases/create.md#agent-compatible-minimal-transition)
only when an explicit model-free normalization is needed.
Never change the KB implicitly or add a model as a workaround.
Only when authenticated Foundry MCP is unavailable or lacks a required operation,
load [typed Prompt SDK fallback](connect-prompt-sdk-fallback.md).
Denial/conflict blocks. Bind the surface; switching requires fresh review, never bypass.

## Proposed plan

List delta, API, identity/scope, network/data, cost, verification, owner
and retained IDs.

## Confirmation

Approve concrete changes once; `plan_fingerprint` stays internal, with
`cleanup_approved: false`. Delegated creation is separate. A Hosted principal
known only after deploy requires a separate RBAC plan. Material/protected-state
drift invalidates approval; disclose bounded Prompt warnings below.

## Mutation

After confirmation, use exact identities; never retry another name.

**Prompt:** Use the planned MCP or SDK surface; never invent operations.
Reconcile one `2025-10-01-preview`
`RemoteTool` connection with `ProjectManagedIdentity`, Search audience, and the
`2026-08-01-preview` KB MCP endpoint. Require the exact Search-service-scoped
`Search Index Data Reader` assignment to observed PROJECT `identity.principalId`,
not agent identity. Preserve all fields; add/switch at most one
same-label `MCPTool` with exact endpoint/connection,
`allowed_tools: ["knowledge_base_retrieve"]`, and `require_approval: "never"`.
Under the same agent name, require retrieval for every question, including
unrelated questions. Answer from retrieved evidence, not general knowledge;
unsupported answers are exactly `I don't know` without citations;
retrieval errors must remain errors. Approve exact appended instructions;
preserve previous instructions/versions. Duplicate labels block.
Search provisioning alone is not a connection-write blocker when the KB GET is
healthy; warn, never claim retrieval readiness. Failed/auth/deletion states block.

After exact identity/binding checks, `type` metadata differences and boolean
`isSharedToAll: true`-to-`false` restriction warn without rewriting. Missing/malformed
sharing, broader access, wrong target/auth/audience/category/required metadata
block. Apply the same rules to reuse; require actual agent tests below.

**Hosted:** Follow the selected [Hosted connection](connect-hosted.md) procedure.
Only approved missing resources, binding differences and required deployments
are writes; exact existing state skips them all. Never replace agents;
source edits need separate review/handoff.

## Verification

Verify protected fields, a `knowledge_base_retrieve` call with original
citations, and unrelated `I don't know` without citations. Preserve behavior;
rerun with stable IDs and zero configuration writes. Account separately for
requested invocations, conversations/sessions and their usage. Record actual
tool execution and returned evidence separately from answer behavior; unavailable
payloads leave payload-level faithfulness unverified, not an inferred empty result.

## Failure and partial completion

Preserve first status/message/request ID. Denial, conflict, incomplete
delegation, failed citations, unknown principal or drift blocks.
Record writes, evidence, ownership, recovery and warnings; never widen state.

## Cleanup

Separate fingerprinted cleanup deletes only run-owned artifacts in reverse.
Prompt uses `helpers/prompt_cleanup.py` with exact digests. Hosted returns
`hosted-cleanup-unsupported`, zero writes, retaining all resources.
Unclear ownership blocks.

## Return contract

Return `planned`/`completed`/`blocked`/`partial`: exact actions/resources,
invocation/readback evidence, ownership, failure, warnings and cleanup status.

## References

- [Shared audit schemas](../references/platform-contracts.md).
- [Interface versions](../references/platform-interfaces.md).

Authorities: failure/conflict/uncertainty only.

- [Connect Agents to Foundry IQ knowledge bases](https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect)
