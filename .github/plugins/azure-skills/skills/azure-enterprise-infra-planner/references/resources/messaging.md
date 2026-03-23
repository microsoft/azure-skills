# Messaging Resources

| Resource | ARM Type | API Version | CAF Prefix | Naming Scope | Region |
|----------|----------|-------------|------------|--------------|--------|
| Event Grid Topic | `Microsoft.EventGrid/topics` | `2025-02-15` | `evgt` | Region | Mainstream |
| Event Hub | `Microsoft.EventHub/namespaces` | `2024-01-01` | `evhns` | Global | Foundational |
| Service Bus | `Microsoft.ServiceBus/namespaces` | `2024-01-01` | `sbns` | Global | Foundational |

## Documentation

| Resource | Bicep Reference | Service Overview | Naming Rules | Additional |
|----------|----------------|------------------|--------------|------------|
| Event Grid Topic | [2025-02-15](https://learn.microsoft.com/azure/templates/microsoft.eventgrid/topics?pivots=deployment-language-bicep) | [Event Grid overview](https://learn.microsoft.com/azure/event-grid/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsofteventgrid) | [Security and auth](https://learn.microsoft.com/azure/event-grid/security-authentication) |
| Event Hub | [2024-01-01](https://learn.microsoft.com/azure/templates/microsoft.eventhub/namespaces?pivots=deployment-language-bicep) | [Event Hubs overview](https://learn.microsoft.com/azure/event-hubs/event-hubs-about) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsofteventhub) | [Event Hubs tiers](https://learn.microsoft.com/azure/event-hubs/event-hubs-quotas) |
| Service Bus | [2024-01-01](https://learn.microsoft.com/azure/templates/microsoft.servicebus/namespaces?pivots=deployment-language-bicep) | [Service Bus overview](https://learn.microsoft.com/azure/service-bus-messaging/service-bus-messaging-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftservicebus) | [Service Bus tiers](https://learn.microsoft.com/azure/service-bus-messaging/service-bus-premium-messaging) |
