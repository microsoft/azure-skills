# Durable Task Scheduler — JavaScript

## Learn More

- [Durable Task Scheduler documentation](https://learn.microsoft.com/azure/durable-task-scheduler/)
- [Durable Functions JavaScript guide](https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview?tabs=javascript)

## Durable Functions Setup

### Required npm Packages

```json
{
  "dependencies": {
    "@azure/functions": "^4.0.0",
    "durable-functions": "^3.0.0"
  }
}
```

> **💡 Finding latest versions**: Run `npm view durable-functions version` or check [npmjs.com/package/durable-functions](https://www.npmjs.com/package/durable-functions) for the latest stable release.

### host.json

```json
{
  "version": "2.0",
  "extensions": {
    "durableTask": {
      "hubName": "default",
      "storageProvider": {
        "type": "durabletask-scheduler",
        "connectionStringName": "DURABLE_TASK_SCHEDULER_CONNECTION_STRING"
      }
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

### local.settings.json

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "node",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "DURABLE_TASK_SCHEDULER_CONNECTION_STRING": "Endpoint=http://localhost:8080;TaskHub=default;Authentication=None"
  }
}
```

## Minimal Example

```javascript
const { app } = require("@azure/functions");
const df = require("durable-functions");

// Activity
df.app.activity("sayHello", {
  handler: (city) => `Hello ${city}!`,
});

// Orchestrator
df.app.orchestration("myOrchestration", function* (context) {
  const result1 = yield context.df.callActivity("sayHello", "Tokyo");
  const result2 = yield context.df.callActivity("sayHello", "Seattle");
  return `${result1}, ${result2}`;
});

// HTTP Starter
app.http("HttpStart", {
  route: "orchestrators/{orchestrationName}",
  methods: ["POST"],
  authLevel: "function",
  extraInputs: [df.input.durableClient()],
  handler: async (request, context) => {
    const client = df.getClient(context);
    const instanceId = await client.startNew(request.params.orchestrationName);
    return client.createCheckStatusResponse(request, instanceId);
  },
});
```

## Workflow Patterns

### Fan-Out/Fan-In

```javascript
df.app.orchestration("fanOutFanIn", function* (context) {
  const cities = ["Tokyo", "Seattle", "London", "Paris", "Berlin"];

  // Fan-out: schedule all activities in parallel
  const tasks = cities.map((city) => context.df.callActivity("sayHello", city));

  // Fan-in: wait for all to complete
  const results = yield context.df.Task.all(tasks);
  return results;
});
```

### Human Interaction

```javascript
df.app.orchestration("approvalWorkflow", function* (context) {
  yield context.df.callActivity("sendApprovalRequest", context.df.getInput());

  // Wait for approval event with timeout
  const expiration = new Date(context.df.currentUtcDateTime);
  expiration.setDate(expiration.getDate() + 3);

  const approvalTask = context.df.waitForExternalEvent("ApprovalEvent");
  const timeoutTask = context.df.createTimer(expiration);

  const winner = yield context.df.Task.any([approvalTask, timeoutTask]);

  if (winner === approvalTask) {
    return approvalTask.result ? "Approved" : "Rejected";
  }
  return "Timed out";
});
```

## Orchestration Determinism

| ❌ NEVER | ✅ ALWAYS USE |
|----------|--------------|
| `new Date()` | `context.df.currentUtcDateTime` |
| `Math.random()` | Pass random values from activities |
| `setTimeout()` | `context.df.createTimer()` |
| Direct I/O, HTTP, database | `context.df.callActivity()` |

### Replay-Safe Logging

```javascript
df.app.orchestration("myOrchestration", function* (context) {
  if (!context.df.isReplaying) {
    console.log("Started");  // Only logs once, not on replay
  }
  const result = yield context.df.callActivity("myActivity", "input");
  return result;
});
```

## Error Handling & Retry

```javascript
df.app.orchestration("workflowWithRetry", function* (context) {
  const retryOptions = new df.RetryOptions(5000, 3); // firstRetryInterval, maxAttempts
  retryOptions.backoffCoefficient = 2.0;
  retryOptions.maxRetryIntervalInMilliseconds = 60000;

  try {
    const result = yield context.df.callActivityWithRetry(
      "unreliableService",
      retryOptions,
      context.df.getInput()
    );
    return result;
  } catch (ex) {
    context.df.setCustomStatus({ error: ex.message });
    yield context.df.callActivity("compensationActivity", context.df.getInput());
    return "Compensated";
  }
});
```

## Durable Task SDK (Non-Functions)

For applications running outside Azure Functions (containers, VMs, Azure Container Apps, Azure Kubernetes Service):

```javascript
const { createAzureManagedWorkerBuilder, createAzureManagedClient } = require("@microsoft/durabletask-js-azuremanaged");

const connectionString = "Endpoint=http://localhost:8080;Authentication=None;TaskHub=default";

// Activity
const sayHello = async (_ctx, name) => `Hello ${name}!`;

// Orchestrator
const myOrchestration = async function* (ctx, name) {
  const result = yield ctx.callActivity(sayHello, name);
  return result;
};

async function main() {
  // Worker
  const worker = createAzureManagedWorkerBuilder(connectionString)
    .addOrchestrator(myOrchestration)
    .addActivity(sayHello)
    .build();

  await worker.start();

  // Client
  const client = createAzureManagedClient(connectionString);
  const instanceId = await client.scheduleNewOrchestration("myOrchestration", "World");
  const state = await client.waitForOrchestrationCompletion(instanceId, true, 30);
  console.log("Output:", state.serializedOutput);

  await client.stop();
  await worker.stop();
}

main().catch(console.error);
```

