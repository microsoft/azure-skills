# Go — Azure Functions Go Worker Triggers & Bindings

> **Model**: [`github.com/azure/azure-functions-golang-worker`](https://github.com/Azure/azure-functions-golang-worker) (**preview**).
> No `function.json` — triggers are declared in code via `sdk.FunctionApp()` + functional options.
> Entry point: `main.go` calling `worker.Start(app)`.
> Requires **Azure Functions Core Tools ≥ 4.12.1** (`npm i -g azure-functions-core-tools@4 --unsafe-perm true`).

## Project Setup

```bash
func init --worker-runtime go
go get github.com/azure/azure-functions-golang-worker
go mod tidy
```

`func init --worker-runtime go` generates `host.json`, `local.settings.json`, and `.gitignore` pre-wired with `FUNCTIONS_WORKER_RUNTIME=native` and the correct Core Tools settings — avoids manual config drift.

> **`local.settings.json` is local-only** — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-go) is explicit: "this file isn't published to Azure." The values below are for `func start`, not for the deployed app:
> - `FUNCTIONS_WORKER_RUNTIME=native` — tells Core Tools to load the "native" worker (Go plugs in as a language-agnostic native worker). Core Tools then infers Go by finding `go.mod` in the project. On the deployed **Flex Consumption** app, the runtime is configured via `functionAppConfig.runtime` on the ARM/Bicep resource — not as an app setting.
> - `FUNCTIONS_CLI_NATIVE_LANGUAGE=go` — written by `func init --worker-runtime go` but redundant in practice (Core Tools infers Go from `go.mod`). Not consumed by the deployed Functions host.
> - `AzureWebJobsStorage` — leave empty locally when no trigger needs host storage; set to `UseDevelopmentStorage=true` for Azurite. In Azure, provide the equivalent as an app setting (or better, use the identity-based form: `AzureWebJobsStorage__blobServiceUri` + `__credential=managedidentity` + `__clientId`).

### Generated `host.json`

Verified output of `func init --worker-runtime go` (Core Tools 4.12.0) — matches the shared extension bundle range in [code-migration.md](../code-migration.md):

```json
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "excludedTypes": "Request"
      }
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

### Generated `local.settings.json`

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "native",
    "FUNCTIONS_CLI_NATIVE_LANGUAGE": "go",
    "AzureWebJobsStorage": ""
  }
}
```

## Lambda Migration Rules

> Shared rules (bindings over SDKs, latest runtime, identity-first auth) → [global-rules.md](../global-rules.md)

Go-specific:
- **Output bindings other than HTTP are not supported** by the Go worker today. For queue/blob/cosmos/etc. writes, use the Azure SDK for Go directly with `DefaultAzureCredential`.
- **Wrap every user-spawned goroutine** with `sdk.Recover` or `sdk.RecoverTo` — an unrecovered panic in *any* goroutine crashes the whole worker and fails every in-flight invocation on it, not just the one that spawned the goroutine.
- Prefer **core triggers** (typed payloads, no external deps). Use the **Blob extension trigger** (blank import) only when you need a live `*blob.Client` for streaming.
- Log with `slog.InfoContext(ctx, ...)`. The SDK auto-installs an `slog` handler that attaches `invocation_id`, `function_name`, and `trigger_type` to every record.

## HTTP Trigger

```go
import (
    "net/http"
    "github.com/azure/azure-functions-golang-worker/sdk"
    "github.com/azure/azure-functions-golang-worker/worker"
)

func hello(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
    _, _ = w.Write([]byte("Hello from Go!"))
}

func main() {
    app := sdk.FunctionApp()
    app.HTTP("hello", hello,
        sdk.WithMethods("GET", "POST"),
        sdk.WithAuth("anonymous"),
        // sdk.WithRoute("users/{id}"),
    )
    worker.Start(app)
}
```

> The HTTP output binding is attached implicitly — write the response via `http.ResponseWriter`.

> **HTTP middleware and streaming.** For wrapping handlers with middleware (timing, tracing, auth), see the upstream [`samples/middleware`](https://github.com/Azure/azure-functions-golang-worker/tree/main/samples/middleware) sample. For streaming responses (Server-Sent Events, large-object downloads, chunked transfer), see [`samples/httpStreaming`](https://github.com/Azure/azure-functions-golang-worker/tree/main/samples/httpStreaming) — the HTTP path uses a real loopback `http.Server`, so `http.Flusher`, chunked encoding, and trailers work natively.

## Blob Storage (extension trigger)

```go
import (
    "context"
    "github.com/Azure/azure-sdk-for-go/sdk/storage/azblob/blob"
    "github.com/azure/azure-functions-golang-worker/sdk"
    _ "github.com/azure/azure-functions-golang-worker/triggers/blob" // registers factory
    "github.com/azure/azure-functions-golang-worker/worker"
)

func onBlob(ctx context.Context, client *blob.Client) error {
    get, err := client.DownloadStream(ctx, nil)
    if err != nil { return err }
    defer get.Body.Close()
    // stream get.Body — supports GB-scale blobs without buffering through gRPC
    return nil
}

func main() {
    app := sdk.FunctionApp()
    app.Blob("processBlob", onBlob,
        sdk.WithPath("samples-workitems/{name}"),
        sdk.WithConnection("AzureWebJobsStorage"),
        sdk.WithSource("EventGrid"),
    )
    worker.Start(app)
}
```

> **`sdk.WithSource("EventGrid")` needs Flex Consumption infrastructure setup.** When the blob trigger uses EventGrid source on Flex Consumption (the only plan Go supports today), three additional IaC settings are required or events will not be delivered: `alwaysReady: [{ name: 'blob', instanceCount: 1 }]`, the `AzureWebJobsStorage__queueServiceUri` app setting, and an Event Grid subscription authored in Bicep/ARM rather than via the `az` CLI. Full Bicep + RBAC checklist: [lambda-to-functions.md — Flex Consumption + Blob Trigger with EventGrid Source](../lambda-to-functions.md#flex-consumption--blob-trigger-with-eventgrid-source).

## Queue Storage

```go
import (
    "context"
    "github.com/azure/azure-functions-golang-worker/sdk"
    "github.com/azure/azure-functions-golang-worker/sdk/bindings"
)

func onQueue(ctx context.Context, msg bindings.QueueMessage) error {
    // msg.Id, msg.Body, msg.DequeueCount, msg.InsertionTime, ...
    return nil
}

app.Queue("queueFunc", onQueue,
    sdk.WithQueueName("myqueue-items"),
    sdk.WithConnection("AzureWebJobsStorage"),
)
```

## Timer

```go
func onTick(ctx context.Context, t bindings.TimerInfo) error {
    // t.IsPastDue, t.ScheduleStatus.Last, t.ScheduleStatus.Next
    return nil
}

app.Timer("scheduledTask", onTick,
    sdk.WithSchedule("0 */5 * * * *"),
)
```

## Event Grid

```go
func onEvent(ctx context.Context, e bindings.EventGridEvent) error {
    // e.Id, e.EventType, e.Subject, e.EventTime, e.Data (json.RawMessage)
    return nil
}

app.EventGrid("eventGridTrigger", onEvent)
```

## Cosmos DB (Change Feed)

```go
func onChanges(ctx context.Context, docs []bindings.CosmosDocument) error {
    for _, d := range docs {
        _ = d.ID
        _ = d.Data // json.RawMessage — unmarshal into your struct
    }
    return nil
}

app.CosmosDB("docs", onChanges,
    sdk.WithDatabase("ToDoList"),
    sdk.WithContainer("Items"),
    sdk.WithConnection("CosmosDBConnection"),
    sdk.WithCreateLeaseContainerIfNotExists(true),
)
```

## Service Bus

```go
// Queue
func onSBQueue(ctx context.Context, msg bindings.ServiceBusMessage) error {
    // msg.MessageId, msg.Body, msg.DeliveryCount, msg.SessionId, ...
    return nil
}

app.ServiceBusQueue("queueFunc", onSBQueue,
    sdk.WithQueueName("input-queue"),
    sdk.WithConnection("ServiceBusConnection"),
)

// Topic + Subscription
app.ServiceBusTopic("topicFunc", onSBQueue,
    sdk.WithTopicName("orders"),
    sdk.WithSubscriptionName("processor"),
    sdk.WithConnection("ServiceBusConnection"),
)
```

## Event Hubs

```go
func onEventHub(ctx context.Context, e bindings.EventHubMessage) error {
    // e.Body, e.SequenceNumber, e.Offset, e.EnqueuedTimeUtc, e.PartitionKey
    return nil
}

app.EventHub("eventHubTrigger", onEventHub,
    sdk.WithEventHubName("input-hub"),
    sdk.WithConnection("EventHubConnection"),
    sdk.WithConsumerGroup("$Default"),
)
```

## SQL (Change Tracking)

> Enable Change Tracking on the DB and table first
> (`ALTER DATABASE ... SET CHANGE_TRACKING = ON;` then
> `ALTER TABLE dbo.Products ENABLE CHANGE_TRACKING;`).

```go
type Product struct {
    ProductID int    `json:"ProductId"`
    Name      string `json:"Name"`
    Cost      int    `json:"Cost"`
}

func onSQL(ctx context.Context, changes []bindings.SQLChange) error {
    for _, c := range changes {
        var p Product
        if err := json.Unmarshal(c.Item, &p); err != nil { continue }
        _ = c.Operation // Insert | Update | Delete
    }
    return nil
}

app.SQL("productsChanged", onSQL,
    sdk.WithTable("dbo.Products"),
    sdk.WithConnection("AzureWebJobsSqlConnectionString"),
)
```

## I/O Outside of Triggers — Use the Azure SDK for Go

The Go worker is **triggers-only by design**. It ships every trigger the other runtimes have, plus the implicit HTTP response — but no input bindings and no non-HTTP output bindings. This is intentional: writes and lookups use the Azure SDK for Go with `DefaultAzureCredential`, which is the idiomatic Go story.

> Go is the intentional exception to the "bindings over SDKs" rule in [global-rules.md](../global-rules.md). All non-HTTP I/O in a Go Function app goes through the Azure SDK for Go.

| Capability | Available on Go worker? | How to do it in Go |
| --- | --- | --- |
| Triggers (HTTP, Timer, Queue, Blob, Cosmos, ServiceBus, EventHub, EventGrid, SQL) | ✅ | See sections above |
| HTTP response | ✅ | Write via `http.ResponseWriter` |
| Blob / Queue / Table / Cosmos / SB / EH / EG input & output | ❌ (by design) | Azure SDK for Go — see patterns below |

## SDK Patterns for I/O

**Ground rules:**

- Use `DefaultAzureCredential`. On UAMI apps, always pass `ManagedIdentityClientID: os.Getenv("AZURE_CLIENT_ID")` — otherwise it tries SystemAssigned first and fails. See [global-rules.md](../global-rules.md).
- **Construct clients once at package init or in `main`**, not per invocation. The worker hosts many concurrent invocations on one process; per-invocation client construction defeats connection pooling and triggers repeated token acquisition.
- Point every service at its URL via an app setting (e.g., `STORAGE_BLOB_URI=https://myacct.blob.core.windows.net`) — never embed keys.

```go
import (
    "os"
    "github.com/Azure/azure-sdk-for-go/sdk/azidentity"
)

var cred = mustCred()

func mustCred() *azidentity.DefaultAzureCredential {
    c, err := azidentity.NewDefaultAzureCredential(&azidentity.DefaultAzureCredentialOptions{
        ManagedIdentityClientID: os.Getenv("AZURE_CLIENT_ID"),
    })
    if err != nil { panic(err) }
    return c
}
```

### Blob — read & write

```go
import "github.com/Azure/azure-sdk-for-go/sdk/storage/azblob"

var blobs, _ = azblob.NewClient(os.Getenv("STORAGE_BLOB_URI"), cred, nil)

// Read
r, err := blobs.DownloadStream(ctx, "input", "path/name.json", nil)
if err != nil { return err }
defer r.Body.Close()
// stream r.Body

// Write
_, err = blobs.UploadStream(ctx, "output", "path/name.json", body, nil)
```

### Queue — send

```go
import "github.com/Azure/azure-sdk-for-go/sdk/storage/azqueue"

var queue, _ = azqueue.NewQueueClient(
    os.Getenv("STORAGE_QUEUE_URI")+"/outqueue", cred, nil)

_, err := queue.EnqueueMessage(ctx, base64.StdEncoding.EncodeToString(payload), nil)
```

> Storage Queue messages must be Base64-encoded when written via SDK — the queue trigger binding does this for you, but the SDK does not.

### Table — read & upsert

```go
import "github.com/Azure/azure-sdk-for-go/sdk/data/aztables"

var tables, _    = aztables.NewServiceClient(os.Getenv("STORAGE_TABLE_URI"), cred, nil)
var products     = tables.NewClient("Products")

// Read one entity
resp, err := products.GetEntity(ctx, "electronics", "sku-42", nil)
var p Product
_ = json.Unmarshal(resp.Value, &p)

// Upsert
raw, _ := json.Marshal(p)
_, err = products.UpsertEntity(ctx, raw, nil)
```

### Cosmos DB — point read & upsert

```go
import "github.com/Azure/azure-sdk-for-go/sdk/data/azcosmos"

var cosmos, _    = azcosmos.NewClient(os.Getenv("COSMOS_ENDPOINT"), cred, nil)
var container, _ = cosmos.NewContainer("mydb", "Items")

// Point read
pk := azcosmos.NewPartitionKeyString("electronics")
resp, err := container.ReadItem(ctx, pk, "sku-42", nil)

// Upsert
raw, _ := json.Marshal(item)
_, err = container.UpsertItem(ctx, pk, raw, nil)
```

### Service Bus — send

```go
import "github.com/Azure/azure-sdk-for-go/sdk/messaging/azservicebus"

var sb, _     = azservicebus.NewClient(os.Getenv("SERVICEBUS_FQDN"), cred, nil)
var sender, _ = sb.NewSender("outqueue", nil) // or topic name

err := sender.SendMessage(ctx, &azservicebus.Message{Body: payload}, nil)
```

### Event Hubs — send batch

```go
import "github.com/Azure/azure-sdk-for-go/sdk/messaging/azeventhubs"

var producer, _ = azeventhubs.NewProducerClient(
    os.Getenv("EVENTHUBS_FQDN"), "outhub", cred, nil)

batch, _ := producer.NewEventDataBatch(ctx, nil)
_ = batch.AddEventData(&azeventhubs.EventData{Body: payload}, nil)
err := producer.SendEventDataBatch(ctx, batch, nil)
```

### Event Grid — publish

```go
import "github.com/Azure/azure-sdk-for-go/sdk/messaging/eventgrid/azeventgrid"

var eg, _ = azeventgrid.NewClient(os.Getenv("EVENTGRID_ENDPOINT"), cred, nil)

events := []azeventgrid.CloudEvent{{
    Source: to.Ptr("myapp"), Type: to.Ptr("order.created"),
    Data: order, DataContentType: to.Ptr("application/json"),
}}
_, err := eg.PublishCloudEvents(ctx, "mytopic", events, nil)
```

## Core vs Extension Triggers

| Criterion | Core (HTTP, Timer, Queue, CosmosDB, EventGrid, EventHub, ServiceBus, SQL) | Extension (Blob) |
| --- | --- | --- |
| Payload size | Bounded (KB–low MB) | Potentially GBs |
| External SDK required | No | Yes (`azblob`, `azidentity`) |
| Data in gRPC message | Yes — typed struct | No — only metadata |
| Streaming | Not needed | Essential — `client.DownloadStream(...)` |
| Activation | Automatic | Blank import: `_ ".../triggers/blob"` |

## Handler Return Values & Retry Semantics

Every non-HTTP trigger handler returns `error`. The value is interpreted by the Functions **host** (not the Go worker), so the retry and poison-message behavior is identical to what the same trigger would do in any other runtime:

- `return nil` → invocation succeeds; the host advances the checkpoint / acknowledges the message / commits the change-feed lease as appropriate.
- `return err` (non-nil) → invocation fails; the host applies the trigger's built-in retry policy, then routes the message to the trigger-specific poison / dead-letter destination.

| Trigger | Default retry behavior | Poison / dead-letter destination |
|---------|------------------------|-----------------------------------|
| HTTP | No automatic retry — response is returned to the caller | N/A (write status code + body in the handler) |
| Storage Queue | Up to `maxDequeueCount` (default 5) | `<queueName>-poison` queue |
| Service Bus Queue / Topic | Up to `MaxDeliveryCount` (default 10, entity-level) | Entity's dead-letter subqueue |
| Event Grid | Retried by Event Grid (24 h exponential backoff) | Dead-letter destination configured on the subscription |
| Blob (`sdk.WithSource("EventGrid")`) | Retried by Event Grid, same as above | Dead-letter destination on the Event Grid subscription |
| Event Hubs | No per-message retry — checkpoint advances on return | None built-in — implement dead-lettering in the handler |
| Cosmos DB (change feed) | No per-document retry — lease advances on return | None built-in — implement dead-lettering in the handler |
| Timer | No retry — next occurrence fires on schedule | N/A |
| SQL (change tracking) | Per `host.json` retry policy | Per configured retry sink |

Configure `host.json`'s [retry policies](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-error-pages) to override the defaults where the trigger supports it.

**Interaction with panic recovery:** `sdk.RecoverTo` converts a panic in a user-spawned goroutine into a non-nil error on the enclosing handler — which then follows the table above. That's why `sdk.RecoverTo` is the correct choice for "failure should cause a retry"; `sdk.Recover` is for best-effort work where losing the panic (and skipping the retry) is acceptable. See the next section for the full pattern.

## Panic Recovery in Goroutines

An unrecovered panic in **any** goroutine terminates the entire worker process, failing every concurrent invocation across every function on that worker. Always guard goroutines you start yourself.

**Best-effort work** (`sdk.Recover`) — fire-and-forget, keeps the worker alive:

```go
go func() {
    defer sdk.Recover(ctx)  // must be the FIRST defer (runs LAST)
    defer wg.Done()
    warmCache(ctx)
}()
```

**Failure-propagating work** (`sdk.RecoverTo` — preferred pattern uses `errgroup`):

```go
import "golang.org/x/sync/errgroup"

func onEventHub(ctx context.Context, events []bindings.EventHubMessage) error {
    g, ctx := errgroup.WithContext(ctx)
    for _, e := range events {
        e := e
        g.Go(func() (err error) {
            defer sdk.RecoverTo(ctx, &err)
            return process(ctx, e)
        })
    }
    return g.Wait() // non-nil -> invocation fails -> host retries
}
```

## Logging

`slog` handler is installed at package init. Every record automatically carries `invocation_id`, `function_name`, and `trigger_type`.

```go
import "log/slog"

slog.InfoContext(ctx, "processed order", "order_id", id, "amount", amount)
```

Access richer invocation metadata (trace parent, retry count) via `sdk.FromContext(ctx)`.

> **OpenTelemetry & Application Insights export.** The SDK's `slog` handler covers structured logging out of the box. For distributed tracing and Azure Monitor / App Insights export, see the upstream [`samples/otelTracing`](https://github.com/Azure/azure-functions-golang-worker/tree/main/samples/otelTracing) sample (OpenTelemetry instrumentation) and [`samples/collectorToAzureMonitor`](https://github.com/Azure/azure-functions-golang-worker/tree/main/samples/collectorToAzureMonitor) (OTel Collector → App Insights pipeline).

## Build & Hosting Constraints

**Hosting plan**: The Go worker is currently only available on **Flex Consumption**. Consumption, Premium, and Dedicated (App Service) plans are not supported.

**Binary format**: The host expects a **Linux ELF binary named `app`** at the deployment root. `func pack` produces this layout automatically; you don't need to build it yourself for deployment.

**CGO must be disabled** — the Flex Consumption base image does not include a C toolchain, so `CGO_ENABLED=1` binaries fail to start. This means Go packages that require cgo (e.g., certain SQLite drivers, native crypto wrappers) cannot be used; pick pure-Go alternatives.

## Local Run & Deployment

```bash
func start           # auto-compiles the Go module, hosts locally
func pack            # produces a zip with the cross-compiled `app` binary at the root
```

Run `func pack` from a directory scaffolded by `func init --worker-runtime go` — it handles the `CGO_ENABLED=0 GOOS=linux GOARCH=amd64` cross-compile and packages the artifact for you. The resulting zip works with any Functions deployment path: `azd deploy`, `func azure functionapp publish`, or [zip push deployment](https://learn.microsoft.com/en-us/azure/azure-functions/deployment-zip-push):

```bash
az functionapp deployment source config-zip \
    -g <RG> -n <APP_NAME> --src <appname>.zip
```

> **Hand-rolling the zip?** If you build the deployment zip yourself (e.g., a Windows CI job that skips `func pack`), the `app` entry must carry Unix executable permissions (mode `0755` or `0777`) in the zip's external attributes — this is a zip-format-level bit, not an NTFS ACL. Windows tools like PowerShell's `Compress-Archive` and Explorer's "Send to → Compressed folder" emit DOS-mode zips with no Unix permission bits; the host will fail to exec `app` on Linux with a permission-denied error. Use `func pack` (works on any host OS and stamps the bits correctly), WSL's `zip`, or a CI step that explicitly sets the executable bit.

> Full reference: [Azure Functions Go developer guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-go) — and the [azure-functions-golang-worker README](https://github.com/Azure/azure-functions-golang-worker) / [samples/](https://github.com/Azure/azure-functions-golang-worker/tree/main/samples) for the preview SDK surface.
