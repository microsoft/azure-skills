# Plan exact cleanup

## When to use

Optional lifecycle: plan run-created KB/KS and Prompt cleanup.
Read [helper contracts](../helpers/contracts.md).

## Do not use

Not creation, repair, ownership recovery or arbitrary child deletion.
Hosted teardown: `hosted-cleanup-unsupported`.

## Inputs and discovery order

Use request/session/records, then exact Azure readback. Ambiguous names need
one focused question; no subscription inventory/repeated intake. No approval
for planning.

| Input | Why needed | Required? | Discovery order | Safe default | If missing or unanswered | Reconfirmation trigger |
|---|---|---|---|---|---|---|
| Target | Scope | Yes | Request/session/records | None | Select exactly | Scope |
| Owner/records | Proof | Yes | Trusted audit | None | Block | Evidence |
| Bounds | Complete reads | Yes | Explicit/default | 20 pages/500 objects | Block at limit | Bounds |
| Consent | Authority | Before write | Unchanged envelope | Unapproved | No write | Plan/state |

Owner metadata is neither ownership proof nor RBAC. Validate record bindings,
not authenticity: retain original approvals/results and original successful call
records. Never invent provenance or treat equivalent GET as create evidence.
Existing/reused/updated/foreign resources stay unowned. Readiness isn't index
content/ownership. Require original child versions, not guesses.

## Decisions

* KB: delete its definition only; retain sources, generated objects and consumers.
  Retrieval stops; consumers are not detached.
* KS: the existing executor deletes only the source. The service cascades to its
  exact generated index (File), or index, indexer,
  skillset and datasource (Blob/ADLS). Show those names before approval.
  Retain local/Storage originals, accounts, containers, models, services/grants.
  Uploaded File copies and indexed content are deleted.
* Before KS cleanup, enumerate **every page** of KBs in that Search service.
  References block: separately plan/delete an owned KB first;
  never detach outside-plan KBs. Native source in-use rejection remains a
  final guard. Enumerate scoped knowledge sources, indexers and skillsets to
  detect shared children; compare exact child definitions/ETags with original
  snapshots. Unknown consumers, missing objects, denied/partial inventories,
  or changed incarnations block.
* Prompt: delete the connection, optionally preceded by one selected run-created
  version. Preserve containers, other versions, KB, models/grants. Deletion removes that
  version's tool binding; it never edits tools on a retained version.
  Require SDK ≥2.4, unshared state and complete paged agent/toolbox inventories,
  **all versions including drafts**, with exact version GETs.
  Only the selected version may consume it.
  Hosted/workflow/external definitions, unknown tools/skills/policies block.
  Sharing outside this project blocks: project agent inventory cannot prove
  external consumer absence. `isSharedToAll: false` alone is not proof.

## Proposed plan

```text
python helpers/cleanup_plan.py --plan request.json
```

Closed request: `schema_version: "1.0"`, nonempty `owner`, exact `target`,
`creation_input_file`, `creation_receipt_file`. Relative paths resolve beside
the request. Use original producer outputs, not hand-built response JSON.

**Before the original creation**, retain proof with:

```text
python helpers/search_reconcile.py --input approved-kb.json --cleanup-receipt-dir "<absolute-private-directory>"
```

The same flag applies to approved `file_source.py` and `prompt_connect.py`
invocations under `helpers/`.
Use an existing private user-owned directory outside the skill; validate
paths/permissions without ACL changes.
From `cleanup_receipts`, select the target's `verified` receipt.
`acknowledged` is diagnostic, not authority. Immutable receipts contain filtered
hashes/IDs/versions, never CU keys, auth/cookies or credentialized bodies.
The keyless-Blob callback's privacy restriction is unchanged.
Verified proof requires native create acknowledgement plus matching original
readback. Reuse/update, recovery, missing identities/ETags or failed child
readback block; later GETs cannot repair proof. Post-write failures are `partial`;
retain errors/receipts.

Original Blob checkpoints from `blob_source.py --receipt-dir` also work with
`creation_result_file` binding the checkpoint digest. ACK/recovery-only evidence
cannot prove original child versions. Never recreate resources for cleanup proof.

Optional `inventory_limits`: closed integer `max_pages`/`max_resources`, defaults
20/500, maxima 100/5000 per collection; total Prompt versions also bounded.
Connection-only `agent_version` + `agent_creation_receipt_file` select one version;
name comes from the same creation input. Never select automatically.

Closed `target`:

* Search: `type: "knowledge-base"` or `"knowledge-source"`, `endpoint`, `name`,
  `api_version` (`2026-04-01` or `2026-08-01-preview`).
* Prompt: `type: "prompt-agent-version"`, `project_resource_id`,
  `project_endpoint`, `name`, exact numeric `version`.
* Connection: `type: "project-connection"`, same project identity, `name`.
* Hosted: only `type: "hosted"`; blocked.

Initial receipts authorize only their version; native ID/time/definition are
guarded. Retain the container.

## Confirmation

Save only `execution_input` as JSON. Review exact delete/retain/ordering, then
change only `approval.confirmed` from `false` to `true`. Never recalculate hashes.
`plan.cleanup_approved: true` labels a destructive proposal:
it is not consent while envelope approval is false.

## Mutation

Executors: `helpers/search_reconcile.py --input approved-cleanup.json`
or `helpers/prompt_cleanup.py --input approved-cleanup.json`.
No combined creation/cleanup approval. Planners never delete, detach, provision,
change roles, invoke retrieval/models, or auto-approve.

Closed `dependency_guard` snapshots and targets are revalidated immediately before
destruction. For connection+version, check protected state before writing, delete/
verify the version, then rescan consumers before conditional connection DELETE.
Stop on failure; report writes/remaining resources. Never strip guards or
handcraft unguarded legacy envelopes.

## Verification

ETag, fingerprint, identity, definition, sharing, inventory or child drift needs
new planning/approval. These are fresh observations, **not an atomic dependency
lock**; avoid concurrent administration. No force-delete or retry around a
native dependency rejection. After source absence, GET each exact child to verify
the cascade; remaining/unreadable children produce a failure, never child DELETE.

## Failure and partial completion

Denied isn't absent. A definitive target 404 returns `already-absent`, no execution
input and no new ownership; never authorize a future same-name replacement.
Missing referenced/generated objects or incomplete pagination block.
Unsupported enumeration (including drafts) names the missing operation;
never substitute a filtered or partial list.
Execution preserves `blocked`/`partial`; never advance after failed verification
or delete a reused consumer.

## Cleanup

No resources created; no recursive cleanup.
Hosted teardown and arbitrary external consumer discovery remain unsupported.

## Return contract

Exit 0: `planned`/`already-absent`, not cleanup completion.
Exit 2: no-write `blocked` with first failure and retained scope.
`planned` returns exact closed-schema `execution_input`, `plan_fingerprint`,
`executor`, and delete/retain/blocked/ordering in `approval_summary`.

## References

Authorities: failure/conflict/uncertainty only.
[Source cascade/in-use](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-blob#delete-a-knowledge-source),
[paged KB inventory](https://learn.microsoft.com/rest/api/searchservice/knowledge-bases/list),
[paged agents and draft versions](https://learn.microsoft.com/python/api/azure-ai-projects/azure.ai.projects.operations.agentsoperations).
