# .NET Aspire App Deployment

Generate Azure infrastructure for .NET Aspire applications using Azure Developer CLI (azd).

## Overview

.NET Aspire apps define their architecture in an AppHost (typically `apphost.cs` or `Program.cs` in the AppHost project). When deploying to Azure, extract service configurations from:

1. **AppHost code** - Directly parse the builder configuration
2. **Aspire manifest** - Generate via `dotnet run <apphost-project> -- --publisher manifest`

## Key Concepts

### AddDockerfile Services

When an Aspire app uses `AddDockerfile()`, the second parameter specifies the Docker build context:

```csharp
builder.AddDockerfile("servicename", "./path/to/context")
//                                    ^^^^^^^^^^^^^^^^ 
//                                    This is the Docker build context
```

The build context determines:
- Where Docker looks for files during `COPY` commands
- The base directory for all Dockerfile operations
- What should be set as `docker.context` in `azure.yaml`

### Aspire Manifest

Generate the manifest to see the exact build configuration:

```bash
dotnet run <apphost-project> -- --publisher manifest --output-path manifest.json
```

Manifest structure for Dockerfile-based services:
```json
{
  "resources": {
    "servicename": {
      "type": "container.v1",
      "build": {
        "context": "path/to/context",
        "dockerfile": "path/to/context/Dockerfile",
        "args": {
          "ARG_NAME": "value"
        }
      }
    }
  }
}
```

## Generating azure.yaml for Aspire

### Extract Docker Context

For services using `AddDockerfile`:

1. **From AppHost code:**
   ```csharp
   builder.AddDockerfile("ginapp", "./ginapp")
   //      Service name ^^^^^^^^  ^^^^^^^^^^^ Build context
   ```
   
2. **From manifest:**
   ```json
   "ginapp": {
     "build": {
       "context": "samples/container-build/ginapp"
     }
   }
   ```

### Generate azure.yaml Entry

```yaml
services:
  ginapp:
    project: .                    # AppHost project root
    host: containerapp
    image: ginapp                 # Service name from AddDockerfile
    docker:
      path: ginapp/Dockerfile     # Path to Dockerfile (relative to project root)
      context: ginapp             # Build context (relative to project root)
```

### Key Rules

| Rule | Explanation |
|------|-------------|
| **Omit `language`** | Docker handles the build; azd doesn't need language-specific behavior |
| **Use relative paths** | All paths in `azure.yaml` are relative to project root (where azure.yaml lives) |
| **Extract from manifest** | When in doubt, generate the Aspire manifest and use `build.context` |
| **Match Dockerfile expectations** | The `context` must match what the Dockerfile's `COPY` commands expect |

## Common Patterns

### Single Dockerfile Service

**AppHost:**
```csharp
builder.AddDockerfile("api", "./src/api")
```

**azure.yaml:**
```yaml
services:
  api:
    project: .
    host: containerapp
    image: api
    docker:
      path: src/api/Dockerfile
      context: src/api
```

### Multiple Dockerfile Services

**AppHost:**
```csharp
builder.AddDockerfile("frontend", "./src/frontend");
builder.AddDockerfile("backend", "./src/backend");
```

**azure.yaml:**
```yaml
services:
  frontend:
    project: .
    host: containerapp
    image: frontend
    docker:
      path: src/frontend/Dockerfile
      context: src/frontend
  
  backend:
    project: .
    host: containerapp
    image: backend
    docker:
      path: src/backend/Dockerfile
      context: src/backend
```

### Dockerfile in Subdirectory with Root Context

**AppHost:**
```csharp
builder.AddDockerfile("app", ".")  // Root context
```

**azure.yaml:**
```yaml
services:
  app:
    project: .
    host: containerapp
    image: app
    docker:
      path: Dockerfile              # Dockerfile at root
      context: .                    # Build context is root
```

## Error Prevention

### ❌ Common Mistakes

**Missing context causes build failures:**
```yaml
services:
  ginapp:
    project: .
    host: containerapp
    docker:
      path: ginapp/Dockerfile
      # ❌ Missing context - Docker will use ginapp/ as context
      #    but COPY commands expect files from project root
```

**Incorrect language field:**
```yaml
services:
  ginapp:
    project: .
    language: go              # ❌ Not needed for Docker builds
    host: containerapp
    docker:
      path: ginapp/Dockerfile
      context: ginapp
```

### ✅ Correct Configuration

```yaml
services:
  ginapp:
    project: .
    host: containerapp
    image: ginapp
    docker:
      path: ginapp/Dockerfile
      context: ginapp         # ✅ Explicit context matches AppHost
```

## Validation Steps

1. **Check Dockerfile COPY paths** - Ensure they're relative to the specified context
2. **Generate manifest** - Verify `build.context` matches your azure.yaml
3. **Test azd package** - Run `azd package` to validate Docker build succeeds
4. **Review build output** - Check that files are found during COPY commands

## Related Resources

- [azure.yaml Schema](azure-yaml.md)
- [Docker Guide](docker.md)
- [AZD Deployment](../../sdk/azd-deployment.md)
