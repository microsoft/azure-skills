# Resource owner default

Use for an unresolved owner in File, Blob/ADLS or KB intake. An explicit supplied
owner wins. Preserve a resolved owner through handoffs and exact reuse; never
replace it just because the current caller differs. Example owner strings are
placeholders, not defaults.

Reuse the already-read `az account show` result: `user.name`, `user.type` and
`tenantId` together, retaining their Azure caller provenance. If account context
has not been read, the normal intake can read `az account show` once. Do not
repeat successful discovery just to populate an owner or fetch an access token.

For `user.type: user`, default the owner proposal to the observed UPN/name or
suitable stable user identifier. Show that value and its caller/tenant context
in the consolidated plan/confirmation, allow override, and do not add a separate
redundant owner question. Do not infer an owner from OS/git identity or guess
an email address. Avoid extraneous Graph lookup when account readback supplies
a suitable owner.

For a service principal or managed identity, never invent a human owner.
Use an observed stable principal owner label only when a nonhuman owner is
appropriate to the task or explicitly selected. A generic label such as
`systemAssignedIdentity` alone is not a stable principal identifier. Otherwise,
ask one focused owner decision, retaining all other resolved choices.
An application ID is not automatically a role-assignment principal object ID.

Missing, failed, malformed or ambiguous caller readback: explain exactly what is
unknown and ask one focused owner decision. Unknown caller type or uncertain
tenant applicability is not evidence of a human identity. No silent fake fallback,
login or context switch. An explicit owner resolves this metadata choice, not a
separate authentication/access blocker.

Owner metadata is NOT proof of resource ownership, deletion rights,
role-assignment permission or consent. Keep actual ownership/access readbacks,
concrete-plan approval and separate cleanup approval unchanged. The default is
a proposal, not permission to mutate; helpers still receive an explicit owner.
