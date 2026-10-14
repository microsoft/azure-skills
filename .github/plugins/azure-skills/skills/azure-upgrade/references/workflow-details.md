# Workflow Details

## Upgrade Workflow Phases

The azure-upgrade skill follows a structured workflow to ensure safe, repeatable upgrades.

## Phase Overview

```
┌──────────┐    ┌──────────┐    ┌─────────────┐    ┌─────────┐    ┌──────────┐
│ Identify │───▶│  Assess  │───▶│ Pre-migrate │───▶│ Upgrade │───▶│ Validate │
└──────────┘    └──────────┘    └─────────────┘    └─────────┘    └──────────┘
```

## Progress Tracking

Create and maintain `<UPGRADE_DIR>/upgrade-status.md` (see [Artifact Output Policy](global-rules.md#artifact-output-policy) for path resolution):

```markdown
# Upgrade Status

## Upgrade Details

| Property | Value |
|----------|-------|
| **Source App** | <app-name> |
| **Source Plan** | <current-plan> |
| **Target Plan** | <target-plan> |
| **Resource Group** | <resource-group> |
| **Region** | <region> |
| **Started** | <date> |

## Phase Status

- [ ] Phase 1: Identify — Determine source/target plans
- [ ] Phase 2: Assess — Check readiness and compatibility
- [ ] Phase 3: Pre-migrate — Collect settings and configurations
- [ ] Phase 4: Upgrade — Execute upgrade automation
- [ ] Phase 5: Validate — Verify new app functionality

## Notes

<any issues, decisions, or observations during upgrade>
```

## Error Handling

If any phase fails:
1. Log the error in `<UPGRADE_DIR>/upgrade-status.md`
2. Do NOT proceed to the next phase
3. Inform the user of the failure and suggest remediation
4. Offer to retry the failed phase or rollback

## Hand-off

After successful validation:
- Offer to hand off to `azure-validate` for deeper testing
- Offer to hand off to `azure-deploy` for CI/CD pipeline setup
- Ask about source cleanup only when the scenario confirms production cutover and all cleanup prerequisites are complete. Otherwise state that the source is being retained for rollback.
