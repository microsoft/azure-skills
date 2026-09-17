# Private execution artifacts

Use [private_artifacts.py](private_artifacts.py) before collecting resource-sensitive
planning/receipt data. These commands touch **local storage only**: no Azure calls,
billable queries, approval, login or mutation. Disclose local creation separately
from any subsequent planner discovery or approved Azure mutation.

This is an **operator-selected private directory**, not an automatically managed
workspace for all skill I/O. Only explicitly selected supported outputs/receipts
go there. It does not relocate source documents, intercept every input/output,
provide a full workflow journal or create an OS sandbox.

From the packaged `helpers` directory, replace placeholders with local paths:

```text
python private_artifacts.py --create-directory <absolute-new-private-directory>
python private_artifacts.py --validate-directory <absolute-existing-private-directory>
python file_source.py --plan <request.json> --execution-output <absolute-new-private-file.json>
```

Use native absolute paths, such as `C:\operator\session\private-receipts` on Windows
or `/home/operator/session/private-receipts` on POSIX.
The parent must already exist. Creation makes **one new leaf**; it never fixes or
overwrites an existing directory. Validation accepts only the current operator's
private directory under the existing receipt policy. Use the returned directory
as bootstrap `receipt_dir` or Blob `--receipt-dir`; no manual ACL commands.
If blocked, select another safe parent/new leaf, not the session, home or repository
directory itself. Never recursively change their permissions.

Artifact operations add local filesystem, ACL/ownership and handle checks, JSON
serialization/hashing, integrity readback and flushes; work scales with path depth
and artifact size, including inventories. They make no Azure/model calls.
Planner discovery/inventory costs remain separate. No latency or “negligible
overhead” claim is established by these correctness tests.

## Output and approval

The optional `--execution-output` is supported only with `--plan` in
[File](file_source.py), [Blob](blob_source.py), [KB](search_reconcile.py),
[vector verification](source_vector.py) and [bootstrap](bootstrap_azure.py).
It writes the exact **unapproved execution input**, not the result wrapper.
Preserve null, empty object/array, Unicode, resource bindings and all plan metadata.
Bytes are canonical JSON (sorted keys, ASCII escapes, compact) plus one newline;
`execution_artifact.sha256` hashes those bytes, while `fingerprint` is the existing
`sha256:` plan digest. No implicit approval or executor invocation.

Stdout contains a compact artifact reference, both hashes, `confirmed: false`,
bounded counts/execution-required flags and local/Azure side-effect distinctions—not inventories, source
names, prerequisite references or per-file digests. Review the full private
artifact before approval; a hash alone is not a customer-readable approval summary.
Do not copy private JSON into normal logs or conversation. Output filenames/paths
themselves appear in the reference; choose neutral names.

Legacy output without the flag is unchanged. Bootstrap still defaults to the
existing schema-2 `<receipt_dir>/<operation-id>.plan.json` convention; explicit
output selects its plan location but does not redirect its other operation receipts.
Bootstrap reuse remains read-only and requires no execution.

After human approval, preserve the entire plan/fingerprint and change only
`approval.confirmed` to `true` for schema-1 `--input` executors. For bootstrap,
retain the unchanged schema-2 artifact and use its existing `--apply ... --approve`
contract. These are separate consequential steps, **not artifact validation**.
Never run an executor unapproved as a test. Existing immutable acknowledgement,
conditional-write and receipt ownership semantics are unchanged.

## Filesystem safety and recovery

Shared [_bootstrap_io.py](_bootstrap_io.py) creates POSIX leaves at `0700` and
files at `0600`; Windows supplies an explicit protected owner/SYSTEM/Administrators
DACL **at creation**, with inheritable private directory access. Windows `chmod`
is not privacy. Existing directories must pass owner/DACL or owner/mode validation.
Symlink/reparse ancestors, unsafe leaf names and installed-plugin destinations
block. POSIX ancestors must be root/operator-owned and not group/world writable.
Windows ancestor handles prevent rename/deletion substitution while writing;
a readable inherited parent can safely contain a newly protected private leaf.
Ancestor owners must be the operator, SYSTEM, Administrators or Windows'
fixed TrustedInstaller principal. Nontrusted delete/delete-child, write-owner,
write-DACL and generic-all grants block even when the selected leaf is private:
otherwise another principal could replace the retained path after handles close.
This does not relax the operator-owned private-leaf receipt policy.

Artifacts use exclusive private temporary creation, flushed file contents,
integrity readback, no-replacement publication and final identity/link-count/bytes
verification. POSIX publication flushes the directory; Windows renames the owned
write-through handle without closing/reopening its temporary pathname. Existing
files, directories, symlinks and hardlinks are never overwritten.
Only an owned temporary inode can be removed on failure. Unsupported filesystems,
unprovable ACLs or races block; no reported artifact success on failed persistence.
Cleanup preserves the original persistence blocker and reports a sanitized
outcome: removed, already absent, identity changed, inspection unavailable or
removal unconfirmed. Changed/uninspectable entries are not deleted. Cleanup-only
failures also block success; there is no unprotected fallback.
An error after publication can leave the complete private destination: retain it
for operator inspection and select a new filename, never overwrite it on retry.
No guarantee against the operator, system administrator, compromised kernel or
hardware ignoring flush semantics. Files remain private until the operator handles retention.

JSON output is finite, secret-field checked and bounded to 16 MiB. Individual
planner/executor input limits still apply (notably bootstrap's 1 MiB); the helper
does not expand those limits. Credentials, tokens and secret-bearing connection
strings are forbidden; private query text stays inside the artifact.

## Extension contract (future planners)

Prompt/connection/cleanup do not accept this optional flag. Add that wiring only
in a separate integration after this facility merges. A planner may then import `add_execution_output_argument(parser)`,
`validate_execution_output_mode(args)` (before discovery), and
`emit_plan_result(result, args.execution_output, preserve_unapproved_input=...)`.
Pass the original `status: planned` result and its closed schema-1 unapproved
`execution_input`; retain the prior emitter's preservation setting for default
compatibility. Call inside the CLI's `HelperFailure` boundary.
`retain_execution_input(document, absolute_path)` supports existing schema-1/2
closed envelopes and returns only the reference. No planner may supply an approved
envelope, bypass secret checks, invent consent, emit private summaries or invoke
execution here. Add planner-specific exact-artifact and no-execution regressions.
