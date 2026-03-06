# Durable Task Scheduler — Python

## Learn More

- [Durable Task Scheduler documentation](https://learn.microsoft.com/azure/durable-task-scheduler/)
- [Durable Functions Python guide](https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview?tabs=python)

## Durable Functions Setup

### Required Packages

```txt
# requirements.txt
azure-functions
azure-functions-durable
azure-identity
```

> **💡 Finding latest versions**: Run `pip index versions azure-functions-durable` or check [pypi.org/project/azure-functions-durable](https://pypi.org/project/azure-functions-durable/) for the latest stable release.

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

> **💡 NOTE**: Python uses extension bundles, so the storage provider type is `durabletask-scheduler`. .NET isolated uses the NuGet package directly and requires `azureManaged` instead — see [dotnet.md](dotnet.md).

### local.settings.json

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "DURABLE_TASK_SCHEDULER_CONNECTION_STRING": "Endpoint=http://localhost:8080;TaskHub=default;Authentication=None"
  }
}
```

## Minimal Example

```python
import azure.functions as func
import azure.durable_functions as df

my_app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)

# HTTP Starter
@my_app.route(route="orchestrators/{function_name}", methods=["POST"])
@my_app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client):
    function_name = req.route_params.get('function_name')
    instance_id = await client.start_new(function_name)
    return client.create_check_status_response(req, instance_id)

# Orchestrator
@my_app.orchestration_trigger(context_name="context")
def my_orchestration(context: df.DurableOrchestrationContext):
    result1 = yield context.call_activity("say_hello", "Tokyo")
    result2 = yield context.call_activity("say_hello", "Seattle")
    return f"{result1}, {result2}"

# Activity
@my_app.activity_trigger(input_name="name")
def say_hello(name: str) -> str:
    return f"Hello {name}!"
```

## Workflow Patterns

### Fan-Out/Fan-In

```python
@my_app.orchestration_trigger(context_name="context")
def fan_out_fan_in(context: df.DurableOrchestrationContext):
    cities = ["Tokyo", "Seattle", "London", "Paris", "Berlin"]
    
    # Fan-out: schedule all in parallel
    parallel_tasks = []
    for city in cities:
        task = context.call_activity("say_hello", city)
        parallel_tasks.append(task)
    
    # Fan-in: wait for all
    results = yield context.task_all(parallel_tasks)
    return results
```

### Human Interaction

```python
import datetime

@my_app.orchestration_trigger(context_name="context")
def approval_workflow(context: df.DurableOrchestrationContext):
    yield context.call_activity("send_approval_request", context.get_input())
    
    # Wait for approval event with timeout
    timeout = context.current_utc_datetime + datetime.timedelta(days=3)
    approval_task = context.wait_for_external_event("ApprovalEvent")
    timeout_task = context.create_timer(timeout)
    
    winner = yield context.task_any([approval_task, timeout_task])
    
    if winner == approval_task:
        approved = approval_task.result
        return "Approved" if approved else "Rejected"
    return "Timed out"
```

## Orchestration Determinism

| ❌ NEVER | ✅ ALWAYS USE |
|----------|--------------|
| `datetime.now()` | `context.current_utc_datetime` |
| `uuid.uuid4()` | `context.new_uuid()` |
| `random.random()` | Pass random values from activities |
| `time.sleep()` | `context.create_timer()` |
| Direct I/O, HTTP, database | `context.call_activity()` |

### Replay-Safe Logging

```python
import logging

@my_app.orchestration_trigger(context_name="context")
def my_orchestration(context: df.DurableOrchestrationContext):
    # Check if replaying to avoid duplicate logs
    if not context.is_replaying:
        logging.info("Started")  # Only logs once, not on replay
    result = yield context.call_activity("my_activity", "input")
    return result
```

## Error Handling & Retry

```python
retry_options = df.RetryOptions(
    first_retry_interval_in_milliseconds=5000,
    max_number_of_attempts=3,
    backoff_coefficient=2.0,
    max_retry_interval_in_milliseconds=60000
)

@my_app.orchestration_trigger(context_name="context")
def workflow_with_retry(context: df.DurableOrchestrationContext):
    try:
        result = yield context.call_activity_with_retry(
            "unreliable_service", 
            retry_options, 
            context.get_input()
        )
        return result
    except Exception as ex:
        context.set_custom_status({"error": str(ex)})
        yield context.call_activity("compensation_activity", context.get_input())
        return "Compensated"
```

## Durable Task SDK (Non-Functions)

For applications running outside Azure Functions (containers, VMs, Azure Container Apps, Azure Kubernetes Service):

```python
import asyncio
from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker

# Activity function
def say_hello(ctx, name: str) -> str:
    return f"Hello {name}!"

# Orchestrator function
def my_orchestration(ctx, name: str) -> str:
    result = yield ctx.call_activity('say_hello', input=name)
    return result

async def main():
    with DurableTaskSchedulerWorker(
        host_address="http://localhost:8080",
        secure_channel=False,
        taskhub="default"
    ) as worker:
        worker.add_activity(say_hello)
        worker.add_orchestrator(my_orchestration)
        worker.start()

        # Client
        from durabletask.azuremanaged.client import DurableTaskSchedulerClient
        client = DurableTaskSchedulerClient(
            host_address="http://localhost:8080",
            taskhub="default",
            token_credential=None,
            secure_channel=False
        )
        instance_id = client.schedule_new_orchestration("my_orchestration", input="World")
        result = client.wait_for_orchestration_completion(instance_id, timeout=30)
        print(f"Output: {result.serialized_output}")

if __name__ == "__main__":
    asyncio.run(main())
```

