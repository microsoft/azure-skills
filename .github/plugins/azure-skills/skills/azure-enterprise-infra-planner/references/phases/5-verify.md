# Phase 5: Verify Plan

Thoroughly and objectively verify the generated plan based on the following checklists:
- [verification.md](../verification.md)
- [pairing-checks.md](../pairing-checks.md)

Other mandatory areas to check:
- Goal coverage — does every user requirement map to a resource?
- Dependency completeness — every `dependencies[]` entry resolves
- Pairing constraints — SKU compatibility, subnet conflicts, storage pairing

You must fix any issue in-place in the plan JSON.

## Gate
- Every item in **both** checklists pass (or have been fixed).
- Present plan to user and wait for manual and explicit approval before proceeding.
  - Edit `meta.status` to `approved` if approved.
  - Otherwise, ask the user for improvements, and return to Phase 2, 3, or 4 based on the nature of their request.