# Messaging Pairing Constraints

### Event Grid Topic

| Paired With | Constraint |
|-------------|------------|
| **Event Subscriptions** | Subscriptions are child resources. Delivery endpoints include: Webhook, Azure Function, Event Hub, Service Bus Queue/Topic, Storage Queue, Hybrid Connection. |
| **Private Endpoint** | Only available with `Premium` SKU. Set `publicNetworkAccess: 'Disabled'` when using private endpoints exclusively. |
| **Managed Identity** | Required for dead-letter destinations and delivery to Azure resources that require authentication (Event Hub, Service Bus, Storage). |
| **Function App** | Use Event Grid trigger binding. Subscription endpoint type is `AzureFunction`. Function must have Event Grid extension registered. |
| **Event Hub** | Subscription endpoint type is `EventHub`. Provide the Event Hub resource ID. Requires managed identity or connection string. |
| **Storage Queue** | Subscription endpoint type is `StorageQueue`. Provide storage account ID and queue name. |
| **Dead Letter** | Dead-letter destination must be a Storage blob container. Requires managed identity or storage key for access. |

### Event Hub

| Paired With | Constraint |
|-------------|------------|
| **VNet** | Standard, Premium, and Dedicated SKUs support VNet service endpoints and private endpoints. |
| **Zone Redundancy** | Available in Standard (with ≥4 TU recommended) and Premium. |
| **Kafka** | Kafka protocol support available in Standard and Premium only (not Basic). |
| **Capture** | Event capture to Storage/Data Lake available in Standard and Premium only. |
| **Consumer Groups** | Basic: 1 consumer group. Standard: 20. Premium: 100. Dedicated: 1,000. |
| **Retention** | Basic: 1 day. Standard: 1–7 days. Premium: up to 90 days. |
| **Function App** | Event Hub trigger uses connection string or managed identity. Set `EventHubConnection` in app settings. |

### Service Bus

| Paired With | Constraint |
|-------------|------------|
| **Topics** | Only Standard and Premium SKUs support topics and subscriptions. Basic supports queues only. |
| **VNet** | Only Premium SKU supports VNet service endpoints and private endpoints. |
| **Zone Redundancy** | Only Premium SKU supports zone redundancy. |
| **Partitioning** | Premium messaging partitions cannot be changed after creation. |
| **Message Size** | Basic/Standard: max 256 KB. Premium: max 100 MB. Plan accordingly for large payloads. |
| **Function App** | Service Bus trigger uses connection string or managed identity. Set `ServiceBusConnection` in app settings. |
