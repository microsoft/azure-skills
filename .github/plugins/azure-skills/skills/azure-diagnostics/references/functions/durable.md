# Durable Functions Troubleshooting

Diagnostics for stuck orchestrations, non-determinism, and task hub conflicts.

## Stuck Orchestrations

| Symptom | Cause | Fix |
|---------|-------|-----|
| Orchestration stuck in `Running` indefinitely | An awaited durable timer/sub-orchestration/activity never completes, or completes but the orchestrator never observes it due to a non-determinism error breaking replay | Query instance status; check for `OrchestrationServiceException`/replay errors in App Insights `traces` for that `instanceId` |
| Orchestration stuck in `Pending` | Task hub control-queue backlog, host-storage access failure, or the Durable extension isn't loading | Check control queue depth, `AzureWebJobsStorage`, extension startup logs, and scale-controller traces |
| `Terminated`/`Failed` but activity output looks fine | Unhandled exception in the orchestrator itself (not an activity) | Orchestrator-level exceptions fail the whole instance; wrap sub-orchestrator/activity calls in `try/catch` if partial failure should be tolerated |

```bash
# Check one orchestration instance
func durable get-runtime-status --connection-string-setting AzureWebJobsStorage \
  --task-hub-name TASKHUB --id <instance-id> --show-output
```

## Non-Determinism Violations

Orchestrator functions must produce the same durable operations in the same order on replay.
Pure computation is safe; nondeterministic I/O, time, randomness, and unmanaged tasks aren't.

| Anti-pattern | Why It Breaks | Fix |
|--------------|----------------|-----|
| `Thread.Sleep` / `Task.Delay` | Not replay-safe: uses a non-durable wait that isn't persisted, so it isn't recomputed identically on replay | `context.CreateTimer()` |
| `DateTime.Now` / `DateTime.UtcNow` | Returns a different value on every replay | `context.CurrentUtcDateTime` |
| `Guid.NewGuid()` | Generates a new value on every replay | `context.NewGuid()` |
| Direct HTTP/DB calls in the orchestrator body | Side effects re-execute on every replay | Move to an activity function and call it via `context.CallActivityAsync` |
| `async`/`await` on non-Durable-Task APIs (e.g. raw `Task.Run`, unmanaged threads) | Not tracked in the orchestration history, so it can't be replayed consistently | Only await `context.Call*Async`/`context.CreateTimer`/`context.WaitForExternalEvent` inside an orchestrator |

> Search App Insights `exceptions` for `NonDeterministic` when an orchestration silently stalls. The extension logs `NonDeterministicWorkflowException`/replay errors when history and current execution diverge.

## Timeout Patterns: Cancel the Loser, Don't Just Race

A common but incomplete pattern uses `Task.WhenAny` to add a timeout to a
sub-orchestration call, but `Task.WhenAny` only picks a winner. It doesn't cancel the
loser. If the sub-orchestration wins, an outstanding durable timer keeps the parent
instance's history growing until it fires. If the timer wins, the sub-orchestration keeps
running with no caller waiting on it, which can duplicate side effects on retry.

This in-process C# example cancels the timer and assigns a known child ID:

```csharp
using var timeoutCts = new CancellationTokenSource();
var deadline = context.CurrentUtcDateTime.AddMinutes(5);
var childInstanceId = $"{context.InstanceId}:child";
var subTask = context.CallSubOrchestratorAsync<Result>(
    "ChildOrchestrator", childInstanceId, input);
var timeoutTask = context.CreateTimer(deadline, timeoutCts.Token);
var winner = await Task.WhenAny(subTask, timeoutTask);

if (winner == subTask)
{
    timeoutCts.Cancel(); // stop the outstanding timer from lingering in history
    return await subTask;
}

// The child is still running. Include its ID so an external monitor can terminate it.
throw new TimeoutException($"Child orchestration {childInstanceId} timed out.");
```

`context.CreateTimer` accepts a `CancellationToken`; canceling it on the success path
allows the parent to complete without waiting for the timer. `Task.WhenAny` does not cancel
an activity or sub-orchestration. If the child must stop, call `TerminateAsync` (in-process)
or `TerminateInstanceAsync` (isolated worker) from a client-capable function using the known
child ID. Do not inject or call a Durable client from orchestrator code. Termination also
does not stop an activity already executing, so activity side effects must be idempotent or
cooperatively cancellable.

## Task Hub Conflicts

| Symptom | Cause | Fix |
|---------|-------|-----|
| Orchestrations from two apps interleave/corrupt each other's history | Two function apps configured with the same task hub name against the same storage backend | Assign each app a unique task hub name |
| App fails to start after deployment, hub-name-related error | Task hub name isn't alphanumeric, or exceeds 45 characters | Task hub names must be alphanumeric only (letters and numbers, starting with a letter, 3-45 chars). The name prefixes storage artifacts that forbid special characters. `MyApp-TaskHub-Prod` is invalid; use `MyAppTaskHubProd` |
| Duplicate/lost orchestration instances after a shared-storage migration | Multiple apps unintentionally sharing the same storage account and default task hub name | Give each app an explicit, unique `hubName` in `host.json` rather than relying on the default |

```bash
# Check whether a task hub name override is set via app settings
az functionapp config appsettings list -n APP -g RG \
  --query "[?name=='AzureFunctionsJobHost__extensions__durableTask__hubName']" -o table

# If no override is set, the hub name comes from host.json:
#   - Inspect host.json in your source repo, or
#   - Use Kudu (Advanced Tools) / zip-deployed content to view host.json in the deployed app
```

```json
{
  "extensions": {
    "durableTask": {
      "hubName": "MyAppTaskHubProd"
    }
  }
}
```

> **Tip:** For the Azure Storage provider, a task hub uses multiple tables, queues, and
> blobs. See the [storage
> providers docs](https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-storage-providers#azure-storage)
> for the full schema before assuming an artifact is missing.

## Purging Old Instance History

```bash
# Compute a cutoff timestamp 7 days ago, portable across GNU (Linux) and BSD (macOS) date
if CUTOFF=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null); then
  :
else
  CUTOFF=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)
fi

func durable purge-history --connection-string-setting AzureWebJobsStorage \
  --task-hub-name TASKHUB --created-before "$CUTOFF" \
  --runtime-status completed failed terminated canceled
```

Always restrict purge operations to terminal statuses. Without `--runtime-status`, Core
Tools also purges matching active instances.

> ⚠️ **Growing history warning:** Orchestrations with >10,000 history events can hit
> performance/storage limits. To check whether an instance's history is large, query the
> History table for that instance's partition key and count rows. `--num-results 1` only
> confirms the table has entries, it doesn't estimate row count.

## Integration Testing Durable Failure Paths

- **Stuck orchestration**: start an orchestration whose sub-orchestrator never completes; assert the instance stays `Running` and a timeout/terminate recovery path exists.
- **Non-determinism**: introduce `DateTime.UtcNow` into an orchestrator, force a replay, and assert the extension surfaces a non-determinism error rather than silently diverging.
- **Task hub conflict**: in Azurite or isolated test storage, run two apps with the same hub name and assert the collision is detected; never run this test against shared production storage.
- **Timeout/cancellation**: assert that when the timer wins a `Task.WhenAny` race, the losing sub-orchestration is either explicitly terminated or documented as intentionally left running.
