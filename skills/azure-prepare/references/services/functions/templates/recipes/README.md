# Function Template Recipes

Composable templates for Azure Functions integrations.

## Recipe Index

For intent-to-resource mapping and selection algorithm, see [selection.md](../selection.md).

| Recipe | Resource |
|--------|----------|
| [cosmosdb](cosmosdb/README.md) | `cosmos` |
| [eventhubs](eventhubs/README.md) | `eventhub` |
| [servicebus](servicebus/README.md) | `servicebus` |
| [timer](timer/README.md) | `timer` |
| [durable](durable/README.md) | `durable` |
| [mcp](mcp/README.md) | `mcp` |
| [sql](sql/README.md) | `sql` |
| [blob-eventgrid](blob-eventgrid/README.md) | `blob` |

## Composition

See [composition.md](composition.md) for merging multiple templates.

## Common Patterns

| Pattern | Description |
|---------|-------------|
| [Error Handling](common/error-handling.md) | Try/catch + logging patterns |
| [Health Check](common/health-check.md) | Health endpoint for monitoring |
| [Node.js Entry Point](common/nodejs-entry-point.md) | `src/index.js` requirements |
| [.NET Entry Point](common/dotnet-entry-point.md) | `Program.cs` requirements |
