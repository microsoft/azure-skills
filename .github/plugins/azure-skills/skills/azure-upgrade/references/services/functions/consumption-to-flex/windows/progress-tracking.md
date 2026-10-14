# Migration Progress

Maintain `<UPGRADE_DIR>/upgrade-status.md` and show the current status in chat at every transition. The workflow documents are the source of truth; do not maintain a second hard-coded step inventory here.

## Build the Checklist

1. Read the ordered `### Phase` headings in [workflow.md](workflow.md) to determine the phase names and total.
2. Read the ordered workflow-unit table in [automation.md](automation.md). For each phase, load the linked automation files that own its work and add their executable headings in document order. Include conditional and optional headings; mark them skipped only after evaluating their conditions.
3. Use a numbered step label such as `4g` as its stable ID. For unnumbered work, use the exact heading text.
4. On resume, rebuild the workflow snapshot from the current headings and reconcile it with saved state:
   - preserve matching completed, skipped, deferred, blocked, and pending entries;
   - add new headings as pending in document order;
   - record renamed or removed saved entries under Notes instead of silently discarding them.

## Reporting Rules

1. Before each action, update `Current Status` and display: `Phase <current> of <total> · <step> · <description> · <state>`.
2. After success, mark the item complete and immediately display the next item.
3. At an approval gate, use state `awaiting approval` and invoke `ask_user` in the same turn.
4. Mark work `skipped — <reason>` when it is not applicable or the user intentionally omits it and no later action is expected in this migration.
5. Mark work `deferred — <reason>` when it remains outstanding but the user chooses to continue, such as access-restricted HTTP validation or production trigger cutover. Preserve it in the workflow snapshot and summarize it in `Next action` or `Notes`; never represent it as complete.
6. Mark work `blocked` when an intended action cannot proceed because of an error or unresolved dependency. Record the error without secrets and do not advance unless the user explicitly chooses to defer or skip the work.
7. The workflow may advance past skipped or deferred items. A phase may close with those states, but its summary must identify deferred work.
8. Do not report a percentage; validation and cutover duration varies by function count.

## Migration Outcomes

Track an outcome separately from the current step state:

| Outcome | Meaning |
|---------|---------|
| `in progress` | The workflow is still executing or awaiting decisions |
| `validation-only success` | The target was created, configured, deployed, and verified at the agreed scope, but applicable production traffic or trigger cutover remains skipped or deferred |
| `production cutover complete` | All applicable production traffic and triggers use the target, target processing is validated, no production-readiness work remains deferred, and the source no longer processes production workloads |
| `rolled back` | The target migration was abandoned or reversed and the source remains the production app |

Never infer `production cutover complete` from successful resource creation, deployment, ARM health, or partial validation alone. A user may explicitly conclude a test migration as `validation-only success`.

State meanings:

| State | Meaning |
|-------|---------|
| `pending` | Not started |
| `in progress` | Currently executing |
| `awaiting approval` | Waiting at an explicit user decision gate |
| `blocked` | Intended work cannot proceed |
| `skipped` | Not applicable or intentionally omitted; no later action expected |
| `deferred` | Postponed and still outstanding |
| `complete` | Finished and verified |

## Status Template

```markdown
# Windows Consumption to Flex Migration Status

## Current Status

| Property | Value |
|----------|-------|
| Source app | <SOURCE_APP_NAME> |
| Target app | <NEW_APP_NAME or pending> |
| Outcome | in progress / validation-only success / production cutover complete / rolled back |
| Current phase | <current> of <total derived from scenario headings> |
| Current step | <step> |
| State | pending / in progress / awaiting approval / blocked / skipped / deferred / complete |
| Next action | <description> |
| Last updated | <UTC timestamp> |

## Workflow Snapshot

<Populate from the current scenario and automation headings. Nest each phase's executable steps beneath it.>

## Notes

<Decisions, skipped steps, failures, workflow reconciliation, and resumability details. Never record secrets.>
```
