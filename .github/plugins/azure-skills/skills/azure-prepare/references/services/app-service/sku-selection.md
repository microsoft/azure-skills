# App Service SKU Selection

## SKU Comparison Matrix

| Feature | Free (F1) | Basic (B1-B3) | Standard (S1-S3) | Premium (P0v3-P3v3 and P1Mv3-P5Mv3;P0v4-P3v4 and P1Mv4-P5Mv4) | Isolated (I1v2-I6v2) |
|---------|:-:|:-:|:-:|:-:|:-:|
| **Custom domains** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **TLS/SSL bindings** | ❌ | ✅ (SNI) | ✅ (SNI + IP) | ✅ (SNI + IP) | ✅ (SNI + IP) |
| **Deployment slots** | ❌ | ❌ | 5 | 20 | 20 |
| **Auto-scale** | ❌ | ❌ | ✅ (10 inst.) | ✅ (30 inst.) | ✅ (100 inst.) |
| **VNet integration** | ❌ | ✅ | ✅ | ✅ | ✅ (ASE is in VNet) |
| **Private endpoints** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Always On** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Backup/Restore** | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Hybrid Connections** | ❌ | 5 | 25 | 200 | 200 |
| **Traffic Manager** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **SLA** | None | None | 99.95% | 99.95% | 99.95% |

## Pricing Overview

| SKU | vCPU | RAM | Storage | Approx. Monthly Cost |
|-----|------|-----|---------|---------------------|
| F1 | Shared | 1 GB | 1 GB | Free |
| B1 | 1 | 1.75 GB | 10 GB | ~$55 |
| B2 | 2 | 3.5 GB | 10 GB | ~$110 |
| S1 | 1 | 1.75 GB | 50 GB | ~$73 |
| S2 | 2 | 3.5 GB | 50 GB | ~$146 |
| P1v3 | 2 | 8 GB | 250 GB | ~$138 |
| P2v3 | 4 | 16 GB | 250 GB | ~$276 |
| P3v3 | 8 | 32 GB | 250 GB | ~$552 |
| I1v2 | 2 | 8 GB | 1 TB | ~$460 |

> 💡 **Tip:** Figures are representative for **Windows OS** in **Central US**, **as of 2026-04**. Prices vary by region, OS, and offer. Use the [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) for exact figures.

### Save by using Reserved Instances and Savings Plans

Cost savings can be made on Premium V3, Premium V4 and Isolated V2 plans by committing to reserved instances for 1 or 3 year terms, details can found at [https://learn.microsoft.com/azure/cost-management-billing/reservations/prepay-app-service](https://learn.microsoft.com/azure/cost-management-billing/reservations/prepay-app-service).

Alternatively cost savings can be made using [Azure Savings plans](https://learn.microsoft.com/en-us/azure/cost-management-billing/savings-plan/).

## Decision Criteria

```
Production workload?
├─ No → Free (F1) or Basic (B1) for dev/test
└─ Yes
   Need deployment slots, auto-scale, or backups?
   ├─ No → Basic (B1-B3) if budget-constrained (supports VNet integration and Private Endpoints)
   └─ Yes
          Need network isolation (dedicated ASE)?
          ├─ Yes → Isolated (I1v2+)
          └─ No
             Need more than 5 deployment slots or more than 10 instances?
             ├─ Yes → Premium (P1v3+)
             └─ No → Standard (S1-S3) with Private Endpoints and VNet integration
```

## Feature Unlock Summary

Key features unlocked at each tier:

| Upgrade Path | Features Gained |
|-------------|-----------------|
| Free → Basic | Custom domains, TLS/SSL, Always On, VNet Integration, Private Endpoints, Hybrid Connections (5) |
| Basic → Standard | Deployment slots, auto-scale, backups |
| Standard → Premium | More slots (20), higher scale (30 inst.) |
| Premium → Isolated | Full network isolation (ASE), dedicated infrastructure |

## Bicep — App Service Plan with SKU

```bicep
resource appServicePlan 'Microsoft.Web/serverfarms@2025-03-01' = {
  name: planName
  location: location
  sku: {
    name: 'P1v3'
    tier: 'PremiumV3'
    capacity: 2 // number of instances
  }
  kind: 'linux'
  properties: {
    reserved: true // required for Linux
  }
}
```

## Terraform — App Service Plan with SKU

```hcl
resource "azurerm_service_plan" "plan" {
  name                = var.plan_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "P1v3"
}
```

## Scaling Within a Tier

Scale up (change SKU) vs scale out (add instances):

| Strategy | When to Use | How |
|----------|-------------|-----|
| Scale up | App needs more CPU/RAM | Change SKU (e.g., S1 → S2) |
| Scale out | Handle more concurrent load | Increase instance count or enable auto-scale |

> ⚠️ **Warning:** Scaling from one tier family to another (e.g., Standard to Premium) may cause a brief restart. Schedule changes during low-traffic windows.

## Recommendations by Workload

| Workload | Recommended SKU | Reason |
|----------|----------------|--------|
| Personal blog / prototype | F1 or B1 | Minimal cost, no SLA needed |
| Team dev/test | B1-B2 | Always On, custom domain |
| Production API | S1-S3 (P0v3/P0v4+ for higher scale/perf) | Auto-scale, slots, VNet |
| Enterprise with compliance | P1v3+/P1v4+ | Private endpoints, 20 slots, 30 instances |
| Regulated / multi-tenant SaaS | I1v2+ | Full network isolation |
