# Durable Task Scheduler — Java

## Learn More

- [Durable Task Scheduler documentation](https://learn.microsoft.com/azure/durable-task-scheduler/)
- [Durable Functions Java guide](https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview?tabs=java)

## Durable Functions Setup

### Required Maven Dependencies

```xml
<dependencies>
  <dependency>
    <groupId>com.microsoft.azure.functions</groupId>
    <artifactId>azure-functions-java-library</artifactId>
    <version>3.2.3</version>
  </dependency>
  <dependency>
    <groupId>com.microsoft</groupId>
    <artifactId>durabletask-azure-functions</artifactId>
    <version>1.7.0</version>
  </dependency>
</dependencies>
```

> **💡 Finding latest versions**: Search [Maven Central](https://central.sonatype.com/) for `durabletask-azure-functions` (group: `com.microsoft`) to find the current stable version.

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
    "FUNCTIONS_WORKER_RUNTIME": "java",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "DURABLE_TASK_SCHEDULER_CONNECTION_STRING": "Endpoint=http://localhost:8080;TaskHub=default;Authentication=None"
  }
}
```

## Minimal Example

```java
import com.microsoft.azure.functions.*;
import com.microsoft.azure.functions.annotation.*;
import com.microsoft.durabletask.*;
import com.microsoft.durabletask.azurefunctions.*;

public class DurableFunctionsApp {

    @FunctionName("HttpStart")
    public HttpResponseMessage httpStart(
            @HttpTrigger(name = "req", methods = {HttpMethod.POST}, authLevel = AuthorizationLevel.FUNCTION)
            HttpRequestMessage<Void> request,
            @DurableClientInput(name = "durableContext") DurableClientContext durableContext) {
        DurableTaskClient client = durableContext.getClient();
        String instanceId = client.scheduleNewOrchestrationInstance("MyOrchestration");
        return durableContext.createCheckStatusResponse(request, instanceId);
    }

    @FunctionName("MyOrchestration")
    public String myOrchestration(
            @DurableOrchestrationTrigger(name = "ctx") TaskOrchestrationContext ctx) {
        String result1 = ctx.callActivity("SayHello", "Tokyo", String.class).await();
        String result2 = ctx.callActivity("SayHello", "Seattle", String.class).await();
        return result1 + ", " + result2;
    }

    @FunctionName("SayHello")
    public String sayHello(@DurableActivityTrigger(name = "name") String name) {
        return "Hello " + name + "!";
    }
}
```

## Workflow Patterns

### Fan-Out/Fan-In

```java
@FunctionName("FanOutFanIn")
public List<String> fanOutFanIn(
        @DurableOrchestrationTrigger(name = "ctx") TaskOrchestrationContext ctx) {
    String[] cities = {"Tokyo", "Seattle", "London", "Paris", "Berlin"};
    List<Task<String>> parallelTasks = new ArrayList<>();

    // Fan-out: schedule all activities in parallel
    for (String city : cities) {
        parallelTasks.add(ctx.callActivity("SayHello", city, String.class));
    }

    // Fan-in: wait for all to complete
    List<String> results = new ArrayList<>();
    for (Task<String> task : parallelTasks) {
        results.add(task.await());
    }

    return results;
}
```

### Human Interaction

```java
@FunctionName("ApprovalWorkflow")
public String approvalWorkflow(
        @DurableOrchestrationTrigger(name = "ctx") TaskOrchestrationContext ctx) {
    ctx.callActivity("SendApprovalRequest", ctx.getInput(String.class)).await();

    // Wait for approval event with timeout
    Task<Boolean> approvalTask = ctx.waitForExternalEvent("ApprovalEvent", Boolean.class);
    Task<Void> timeoutTask = ctx.createTimer(Duration.ofDays(3));

    Task<?> winner = ctx.anyOf(approvalTask, timeoutTask).await();

    if (winner == approvalTask) {
        return approvalTask.await() ? "Approved" : "Rejected";
    }
    return "Timed out";
}
```

## Orchestration Determinism

| ❌ NEVER | ✅ ALWAYS USE |
|----------|--------------|
| `System.currentTimeMillis()` | `ctx.getCurrentInstant()` |
| `UUID.randomUUID()` | Pass random values from activities |
| `Thread.sleep()` | `ctx.createTimer()` |
| Direct I/O, HTTP, database | `ctx.callActivity()` |

### Replay-Safe Logging

```java
private static final java.util.logging.Logger logger =
    java.util.logging.Logger.getLogger("MyOrchestration");

@FunctionName("MyOrchestration")
public String myOrchestration(
        @DurableOrchestrationTrigger(name = "ctx") TaskOrchestrationContext ctx) {
    // Use isReplaying to avoid duplicate logs
    if (!ctx.getIsReplaying()) {
        logger.info("Started");  // Only logs once, not on replay
    }
    return ctx.callActivity("MyActivity", "input", String.class).await();
}
```

## Error Handling & Retry

```java
@FunctionName("WorkflowWithRetry")
public String workflowWithRetry(
        @DurableOrchestrationTrigger(name = "ctx") TaskOrchestrationContext ctx) {
    TaskOptions retryOptions = new TaskOptions(new RetryPolicy(
        3,  // maxNumberOfAttempts
        Duration.ofSeconds(5)  // firstRetryInterval
    ));

    try {
        return ctx.callActivity("UnreliableService", ctx.getInput(String.class),
                retryOptions, String.class).await();
    } catch (TaskFailedException ex) {
        ctx.setCustomStatus(Map.of("Error", ex.getMessage()));
        ctx.callActivity("CompensationActivity", ctx.getInput(String.class)).await();
        return "Compensated";
    }
}
```

## Durable Task SDK (Non-Functions)

For applications running outside Azure Functions (containers, VMs, Azure Container Apps, Azure Kubernetes Service):

```java
import com.microsoft.durabletask.*;
import com.microsoft.durabletask.azuremanaged.DurableTaskSchedulerWorkerExtensions;
import com.microsoft.durabletask.azuremanaged.DurableTaskSchedulerClientExtensions;

import java.time.Duration;

public class App {
    public static void main(String[] args) throws Exception {
        String connectionString = "Endpoint=http://localhost:8080;TaskHub=default;Authentication=None";

        // Worker
        DurableTaskGrpcWorker worker = DurableTaskSchedulerWorkerExtensions
            .createWorkerBuilder(connectionString)
            .addOrchestration(new TaskOrchestrationFactory() {
                @Override public String getName() { return "MyOrchestration"; }
                @Override public TaskOrchestration create() {
                    return ctx -> {
                        String result = ctx.callActivity("SayHello",
                                ctx.getInput(String.class), String.class).await();
                        ctx.complete(result);
                    };
                }
            })
            .addActivity(new TaskActivityFactory() {
                @Override public String getName() { return "SayHello"; }
                @Override public TaskActivity create() {
                    return ctx -> "Hello " + ctx.getInput(String.class) + "!";
                }
            })
            .build();

        worker.start();

        // Client
        DurableTaskClient client = DurableTaskSchedulerClientExtensions
            .createClientBuilder(connectionString).build();
        String instanceId = client.scheduleNewOrchestrationInstance("MyOrchestration", "World");
        OrchestrationMetadata result = client.waitForInstanceCompletion(
                instanceId, Duration.ofSeconds(30), true);
        System.out.println("Output: " + result.readOutputAs(String.class));

        worker.stop();
    }
}
```

