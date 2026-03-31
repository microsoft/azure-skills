# Azure Resource Limits and Quotas

Check Azure resource availability during azure-prepare workflow. Validate after customer selects region.

## Types

1. **Hard Limits** - Fixed constraints that cannot be changed
2. **Quotas** - Subscription limits that can be increased via support request

**CLI First:** Always use `az quota` CLI for quota checks. Provides better error handling and consistent output. "No Limit" in REST/Portal doesn't mean unlimited - verify with service docs.

## Hard Limits

Fixed service constraints (cannot be changed).

**Check via**: `azure__documentation` tool or azure-provisioning-limit skill

**Examples**: Cosmos DB item size (2 MB), Container Apps HTTP timeout (240s), App Service Free tier deployment slots (0)

**Process**:
1. Identify services and resource sizes needed
2. Look up limits in documentation
3. Compare plan vs limits
4. If exceeded: redesign or change tier

## Quotas

Subscription/regional limits that can be increased via support request.

**Check via**: `az quota` CLI (install: `az extension add --name quota`)

**Examples**: AKS clusters (5,000/region), Storage accounts (250/region), Container Apps environments (50/region)

**Key Concept**: No 1:1 mapping between ARM resource types and quota names.
- ARM: `Microsoft.App/managedEnvironments` → Quota: `ManagedEnvironmentCount`
- ARM: `Microsoft.Compute/virtualMachines` → Quota: `standardDSv3Family`, `cores`, `virtualMachines`

**Process**:
1. Install extension: `az extension add --name quota`
2. Discover quota names: `az quota list --scope /subscriptions/{id}/providers/{Provider}/locations/{region}`
3. Check usage: `az quota usage show --resource-name {name} --scope ...`
4. Check limit: `az quota show --resource-name {name} --scope ...`
5. Calculate: Available = Limit - Current Usage
6. If exceeded: Request increase via `az quota update`

**Unsupported Providers** (BadRequest error):

Not all providers support quota API. If `az quota list` fails with BadRequest, use fallback:

1. Get current usage:
   ```bash
   # Option A: Azure Resource Graph (recommended)
   az extension add --name resource-graph
   az graph query -q "resources | where type == '{type}' and location == '{loc}' | count"
   
   # Option B: Resource list
   az resource list --subscription "{id}" --resource-type "{Type}" --location "{loc}" | jq 'length'
   ```
2. Get limit from [service documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits)
3. Calculate: Available = Documented Limit - Current Usage

**Known Support Status**:
- ❌ Microsoft.DocumentDB (Cosmos DB)
- ✅ Microsoft.Compute, Microsoft.Network, Microsoft.App, Microsoft.Storage, Microsoft.MachineLearningServices

## Workflow

**Phase 1: Identify & Check Hard Limits**
1. Analyze app requirements and select Azure services
2. Determine resource counts, sizes, tiers, throughput
3. Check hard limits via azure-provisioning-limit skill or documentation
4. Validate plan against limits; redesign if needed

**Phase 2: Check Quotas After Region Selection**
1. Get customer subscription and region preference
2. For each service/region, check quota:
   - Use `az quota usage list` and `az quota show`
   - Calculate available capacity
3. If quota exceeded: request increase or choose different region

**Phase 3: Validate Region**
- Confirm sufficient quota in selected region
- Request increases if needed
- Only proceed after validation complete

## Limit Scopes

| Scope | Example |
|-------|---------|
| Subscription | 50 Cosmos DB accounts (any region) |
| Regional | 250 storage accounts per region |
| Resource | 500 apps per Container Apps environment |

## Service Patterns

| Service | Hard Limits (examples) | Quota Check | Notes |
|---------|------------------------|-------------|-------|
| **Cosmos DB** | Item: 2MB, Partition key: 2KB, Serverless storage: 50GB | ❌ Not supported. Use Resource Graph + [docs](https://learn.microsoft.com/en-us/azure/cosmos-db/concepts-limits). Default: 50 accounts/region | Query: `az graph query -q "resources \| where type == 'microsoft.documentdb/databaseaccounts' and location == 'eastus' \| count"` |
| **AKS** | Pods/node (Azure CNI): 250, Node pools/cluster: 100 | ✅ `az quota` supported | Provider: Microsoft.ContainerService |
| **Storage** | Block blob: 190.7 TiB, Page blob: 8 TiB | ✅ Quota: `StorageAccounts` (limit: 250/region) | Provider: Microsoft.Storage |
| **Container Apps** | Revisions/app: 100, HTTP timeout: 240s | ✅ Quota: `ManagedEnvironmentCount` (limit: 50/region) | Provider: Microsoft.App |
| **Functions** | Timeout (Consumption): 10 min, Queue msg: 64KB | ✅ Check function apps quota | Provider: Microsoft.Web |

## CLI Reference

**Prerequisites**: `az extension add --name quota`

**Discovery**: List quotas to find resource names
```bash
az quota list --scope /subscriptions/{id}/providers/{provider}/locations/{location}
```

**Check Usage**:
```bash
az quota usage show --resource-name {quota-name} --scope /subscriptions/{id}/providers/{provider}/locations/{location}
```

**Check Limit**:
```bash
az quota show --resource-name {quota-name} --scope /subscriptions/{id}/providers/{provider}/locations/{location}
```

**Request Increase**:
```bash
az quota update --resource-name {quota-name} --scope /subscriptions/{id}/providers/{provider}/locations/{location} --limit-object value={new-limit} --resource-type {type}
```

## azure-prepare Integration

**When to Check**:
1. After selecting services - Check hard limits
2. After customer selects region - Check quotas
3. Before generating infrastructure code - Validate availability

**Required Steps**:

**Phase 1 - Planning**:
- Select Azure services
- Check hard limits (service documentation)
- Create provisioning limit checklist (leave quota columns as "_TBD_")

**Phase 2 - Execution**:
- Get subscription and region preference
- **Must invoke azure-quotas skill** - Process ONE resource type at a time:
  a. Try `az quota list` first (required)
  b. If supported: Use `az quota usage show` and `az quota show`
  c. If NOT supported (BadRequest): Use Resource Graph + service docs
  d. Calculate available capacity
  e. Document in checklist (no "_TBD_" entries allowed)
  f. If insufficient: Request increase or change region

**Phase 3 - Generate Artifacts**:
- Only proceed after Phase 2 complete (all quotas validated)

## Error Messages

| Error | Type | Action |
|-------|------|--------|
| "Quota exceeded" | Quota | Use azure-quotas to request increase |
| "(BadRequest) Bad request" | Unsupported provider | Use [service limits docs](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits) |
| "Limit exceeded" | Hard Limit | Redesign or change tier |
| "Maximum size exceeded" | Hard Limit | Split data or use alternative storage |
| "Too many requests" | Rate Limit | Implement retry logic or increase tier |
| "Cannot exceed X" | Hard Limit | Stay within limit or use multiple resources |
| "Subscription limit reached" | Quota | Request quota increase using azure-quotas skill |
| "Regional capacity" | Quota | Choose different region or request increase |

## Best Practices

1. **MUST use Azure CLI quota API first**: `az quota` commands are MANDATORY as the primary method for checking quotas - only use fallback methods (REST API, Portal, docs) when quota API returns `BadRequest`
2. **Don't trust "No Limit" values**: If REST API or Portal shows "No Limit" or unlimited, verify with official service documentation - it likely means the quota API doesn't support that resource type, not that capacity is unlimited
3. **Always check after customer selects region**: Validates availability and allows time for quota requests
4. **Use the discovery workflow**: Never assume quota resource names - always run `az quota list` first to discover correct names
5. **Check both usage and limit**: Run `az quota usage show` AND `az quota show` to calculate available capacity
6. **Handle unsupported providers gracefully**: If you get `BadRequest` error, fall back to official documentation (Azure Resource Graph + docs)
7. **Request quota increases proactively**: If selected region lacks capacity, submit request before deployment
8. **Have alternative regions ready**: If quota increase denied, suggest backup regions
9. **Document capacity assumptions**: Note quota availability and source in `.azure/deployment-plan.md`
10. **Design for limits**: Architecture should account for both hard limits and quotas
11. **Monitor usage trends**: Regular quota checks help predict future needs
12. **Use lower environments wisely**: Dev/test environments count against quotas

## Quick Reference Limits

For complete quota checking workflow and commands, invoke the **azure-quotas** skill.

> **Note:** These are typical default limits. Always verify actual quotas using `az quota show` for your specific subscription and region.

Common quotas to check:

### Subscription Level
- Cosmos DB accounts: 50 per region (check via docs - quota API not supported)
- SQL logical servers: 250 per region
- Service Bus namespaces: 100-1,000 (tier dependent)

### Regional Level  
- Storage accounts: 250 per region (quota resource name: `StorageAccounts`)
- AKS clusters: 5,000 per region (quota resource name: varies by configuration)
- Container Apps environments: 50 per region (quota resource name: `ManagedEnvironmentCount`)
- Function apps: 200 per region (Consumption)

### Resource Level
- Cosmos DB containers per account: Unlimited (subject to storage)
- Apps per Container Apps environment: 500
- Databases per SQL server: 500
- Queues/topics per Service Bus namespace: 10,000

## Related Documentation

- **azure-quotas skill** - Complete quota checking workflow and CLI commands (invoke the **azure-quotas** skill)
- [Azure subscription limits](https://learn.microsoft.com/azure/azure-resource-manager/management/azure-subscription-service-limits) - Official Microsoft documentation
- [Azure Quotas Overview](https://learn.microsoft.com/en-us/azure/quotas/quotas-overview) - Understanding quotas and limits
- [azure-context.md](azure-context.md) - How to confirm subscription and region
- [architecture.md](architecture.md) - Architecture planning workflow

## Example: Complete Check Workflow

```bash
# Scenario: Deploying app with Cosmos DB, Storage, and Container Apps
# Customer selected region: East US

# 1. Check Hard Limits (from azure-provisioning-limit skill)
# Cosmos DB: Item size max 2 MB ✓
# Storage: Blob size max 190.7 TiB ✓
# Container Apps: Timeout 240 sec ✓

# 2. Get Customer's Region Preference
# Customer: "I prefer East US"

# 3. Check Quotas for Customer's Selected Region (East US)

# 3a. Cosmos DB - NOT SUPPORTED by quota API
az quota list \
  --scope /subscriptions/abc-123/providers/Microsoft.DocumentDB/locations/eastus
# Error: (BadRequest) Bad request

# Fallback: Get current usage with Azure Resource Graph
# Install extension first (if needed)
az extension add --name resource-graph

az graph query -q "resources | where type == 'microsoft.documentdb/databaseaccounts' and location == 'eastus' | count"
# Result: 3 database accounts currently deployed

# Or use Azure CLI resource list
az resource list \
  --subscription "abc-123" \
  --resource-type "Microsoft.DocumentDB/databaseAccounts" \
  --location "eastus" | jq 'length'
# Result: 3

# Get limit from documentation: 50 database accounts per region
# Calculate: Available = 50 - 3 = 47 ✓
# Document as: "Fetched from: Azure Resource Graph + Official docs"

# 3b. Storage Accounts
# Step 1: Discover resource name
az quota list \
  --scope /subscriptions/abc-123/providers/Microsoft.Storage/locations/eastus

# Step 2: Check usage (use discovered name "StorageAccounts")
az quota usage show \
  --resource-name StorageAccounts \
  --scope /subscriptions/abc-123/providers/Microsoft.Storage/locations/eastus
# Current: 180

# Step 3: Check limit
az quota show \
  --resource-name StorageAccounts \
  --scope /subscriptions/abc-123/providers/Microsoft.Storage/locations/eastus
# Limit: 250
# Available: 250 - 180 = 70 ✓

# 3c. Container Apps
# Step 1: Discover resource name
az quota list \
  --scope /subscriptions/abc-123/providers/Microsoft.App/locations/eastus
# Shows: "ManagedEnvironmentCount"

# Step 2: Check usage
az quota usage show \
  --resource-name ManagedEnvironmentCount \
  --scope /subscriptions/abc-123/providers/Microsoft.App/locations/eastus
# Current: 8

# Step 3: Check limit
az quota show \
  --resource-name ManagedEnvironmentCount \
  --scope /subscriptions/abc-123/providers/Microsoft.App/locations/eastus
# Limit: 50
# Available: 50 - 8 = 42 ✓

# 4. Validate Availability
# ✅ All services have sufficient quota in East US
# ✅ Proceed with deployment

# Alternative: If quotas were insufficient
# ❌ Container Apps: 49/50 (only 1 available, need 3)
# Action: Request quota increase
# 
# az quota update \
#   --resource-name ManagedEnvironmentCount \
#   --scope /subscriptions/abc-123/providers/Microsoft.App/locations/eastus \
#   --limit-object value=100 \
#   --resource-type Microsoft.App/managedEnvironments
```

---

> **Remember**: Checking limits and quotas early prevents deployment failures and ensures smooth infrastructure provisioning.
