# Container Apps Revision Management

Revisions are immutable snapshots of a Container App version. Use them for blue/green deployments, canary releases, and instant rollback.

## Revision Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `Single` | New revision replaces old immediately | Simple apps, dev/test |
| `Multiple` | Multiple revisions run simultaneously with traffic splitting | Production blue/green, canary |

## Setting Revision Mode (Bicep)

```bicep
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    configuration: {
      activeRevisionsMode: 'Multiple'
      ingress: {
        external: true
        targetPort: 8080
        traffic: [
          { latestRevision: true, weight: 100 }
        ]
      }
    }
  }
}
```

> 💡 **Tip:** In Bicep/ARM deployments, you typically can't predictably target a specific new revision name. Use `latestRevision: true` in Bicep for initial deployment, then configure traffic splitting or labels via CLI after the new revision is created.

> ⚠️ **Warning:** For blue/green workflows, you must first pin traffic to a named revision before deploying a new one. With `latestRevision: true, weight: 100`, new revisions automatically receive all traffic — there is no validation window.

## Traffic Splitting Patterns

### Blue/Green Deployment

Pin traffic to the current revision, deploy a new one, validate, then switch:

```bash
# Deploy new revision and capture its name from the update output
NEW_REV=$(az containerapp update -n $APP -g $RG --image $NEW_IMAGE \
  --query properties.latestRevisionName -o tsv)

# Test the new revision directly via its revision-specific URL
az containerapp revision list -n $APP -g $RG -o table

# Switch 100% traffic to the new revision
az containerapp ingress traffic set -n $APP -g $RG \
  --revision-weight "$NEW_REV=100"
```

### Canary Release

Gradually shift traffic to validate the new revision under load:

| Phase | Current | Canary | Duration |
|-------|---------|--------|----------|
| 1 | 90% | 10% | 15 min |
| 2 | 50% | 50% | 30 min |
| 3 | 0% | 100% | — |

```bash
# List revisions to identify current stable and new canary
az containerapp revision list -n $APP -g $RG -o table

STABLE_REV=<stable-revision-name>
CANARY_REV=<canary-revision-name>

az containerapp ingress traffic set -n $APP -g $RG \
  --revision-weight "$STABLE_REV=90" "$CANARY_REV=10"
```

### Label-Based Routing

Use labels instead of revision names for stable references:

```bash
# Assign labels
az containerapp revision label add -n $APP -g $RG \
  --label stable --revision "$APP--v1"
az containerapp revision label add -n $APP -g $RG \
  --label canary --revision "$APP--v2"

# Route by label
az containerapp ingress traffic set -n $APP -g $RG \
  --label-weight stable=80 canary=20
```

> 💡 **Tip:** Label-based routing lets you swap revision targets without changing traffic rules.

## Rollback

Revert instantly by redirecting all traffic to a known-good revision (e.g., one labeled `stable`):

```bash
# List active revisions and identify the known-good one
az containerapp revision list -n $APP -g $RG -o table

# Roll back using label-based routing (preferred)
az containerapp ingress traffic set -n $APP -g $RG \
  --label-weight stable=100

# Or roll back to a specific revision by name
az containerapp ingress traffic set -n $APP -g $RG \
  --revision-weight "<known-good-revision-name>=100"
```

## Revision Lifecycle

| Action | Command |
|--------|---------|
| List revisions | `az containerapp revision list -n $APP -g $RG` |
| Show revision details | `az containerapp revision show -n $APP -g $RG --revision $REV` |
| Activate a revision | `az containerapp revision activate -n $APP -g $RG --revision $REV` |
| Deactivate a revision | `az containerapp revision deactivate -n $APP -g $RG --revision $REV` |
| Restart a revision | `az containerapp revision restart -n $APP -g $RG --revision $REV` |

> ⚠️ **Warning:** Deactivated revisions cannot receive traffic. Reactivate before routing traffic to them.

## Terraform Traffic Config

```hcl
resource "azurerm_container_app" "app" {
  name                         = var.app_name
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Multiple"

  ingress {
    external_enabled = true
    target_port      = 8080
    traffic_weight {
      label           = "stable"
      revision_suffix = "v1"
      percentage      = 80
    }
    traffic_weight {
      label           = "canary"
      revision_suffix = "v2"
      percentage      = 20
    }
  }
}
```

## Recommendations

| Scenario | Revision Mode | Traffic Strategy |
|----------|---------------|------------------|
| Dev/Test | Single | N/A — auto-replace |
| Prod API | Multiple | Blue/green with instant swap |
| High-risk change | Multiple | Canary (10% → 50% → 100%) |
| Feature flags | Multiple | Label-based routing |
