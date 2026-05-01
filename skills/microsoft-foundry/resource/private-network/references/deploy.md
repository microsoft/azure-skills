# Deploy & Track

Applies to all private network deployments.

## Deploy

```bash
az deployment group create \
  --resource-group <rg> \
  --template-file main.bicep \
  --parameters main.bicepparam \
  --name <deployment-name>
```

> ⚠️ Capability host provisioning is **asynchronous** (10–20 min). The CLI produces no output during this phase.

## Monitor Progress

Use exponential backoff — do NOT poll every 30 seconds.

| Poll | Wait |
|------|------|
| 1st | 1 min after deploy starts |
| 2nd | 3 min after 1st |
| 3rd | 5 min after 2nd |
| 4th+ | Every 5 min |

```bash
# Overall state
az deployment group show \
  --resource-group <rg> --name <deployment-name> \
  --query "{state:properties.provisioningState,error:properties.error}" -o json

# Per-resource progress
az deployment operation group list \
  --resource-group <rg> --name <deployment-name> \
  --query "[].{resource:properties.targetResource.resourceType,state:properties.provisioningState}" -o table
```

Or block with timeout:

```bash
az deployment group wait \
  --resource-group <rg> --name <deployment-name> \
  --created --timeout 1800
```

## Error Recovery

When a deployment fails, follow this workflow:

### Step 1 — Identify the error

```bash
az deployment operation group list \
  --resource-group <rg> \
  --name <deployment-name> \
  --query "[?properties.provisioningState=='Failed'].{resource:properties.targetResource.resourceType,error:properties.statusMessage}" \
  -o json
```

### Step 2 — Resolve

Use `microsoft_docs_search` with the error code or message to find current remediation. The legionservicelink retry rule is documented in the main workflow's Error Handling section.

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `legionservicelink` / subnet in use | Orphaned service link from prior attempt | Use a new `vnetName` — do not reuse the prior VNet |
| `AuthorizationFailed` on `validate/action` | Missing Contributor role | Assign Contributor + User Access Administrator to deploying identity |
| `SubnetDelegationAlreadyExists` | Agent subnet already delegated to another resource | Use a new VNet or open a support ticket to remove the delegation |
| `disableLocalAuth` policy violation | Template defaults to `false` | Set `disableLocalAuth: true` in Bicep params |
| `defaultOutboundAccess` policy violation | Subnets missing the property | Add `defaultOutboundAccess: false` to subnet properties |

### Step 3 — Present fix to user and get approval

Before re-deploying, show the user:
- What failed and why
- What file/parameter will be changed
- The new `vnetName` to use (must be different from the failed run)

### Step 4 — Re-deploy with a new deployment name

```bash
# Update main.bicepparam: change vnetName to a new unique name
az deployment group create \
  --resource-group <rg> \
  --template-file main.bicep \
  --parameters main.bicepparam \
  --name <deployment-name>-retry
```
