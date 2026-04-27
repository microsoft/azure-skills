# .NET Aspire Projects with AZD

**⛔ MANDATORY: For .NET Aspire projects, NEVER manually create azure.yaml. Use `azd init --from-code` instead.**

## Detection

| Indicator | How to Detect |
|-----------|---------------|
| `*.AppHost.csproj` | `find . -name "*.AppHost.csproj"` |
| `Aspire.Hosting` package | `grep -r "Aspire\.Hosting" . --include="*.csproj"` |
| `Aspire.AppHost.Sdk` | `grep -r "Aspire\.AppHost\.Sdk" . --include="*.csproj"` |

## Workflow

### ⛔ DO NOT (Wrong Approach)

```yaml
# ❌ WRONG - Missing services section
name: aspire-app
metadata:
  template: azd-init
# Results in: "Could not find infra\main.bicep" error
```

### ✅ DO (Correct Approach)

```bash
# Generate environment name
ENV_NAME="$(basename "$PWD" | tr '[:upper:]' '[:lower:]' | tr ' _' '-')-dev"

# Use azd init with auto-detection
azd init --from-code -e "$ENV_NAME"
```

**Generated azure.yaml:**
```yaml
name: aspire-app
metadata:
  template: azd-init
services:
  app:
    language: dotnet
    project: ./MyApp.AppHost/MyApp.AppHost.csproj
    host: containerapp
```

> 💡 **AddDockerfile services:** If the AppHost uses `AddDockerfile()` (e.g., `builder.AddDockerfile("ginapp", "./ginapp")`), do NOT add separate service entries for those resources. Aspire handles container builds for `AddDockerfile` resources at runtime through the AppHost. The `azure.yaml` should contain only the single `app` service pointing to the AppHost.

> ⛔ **BEFORE continuing:** Complete the mandatory [AddParameter + WithBuildArg scan](#after-azd-init-fix-addparameter-used-with-withbuildarg-before-builddeploy) below. Skipping this step is the #1 cause of failed Aspire container-build deployments.

## Command Flags

| Flag | Required | Purpose |
|------|----------|---------|
| `--from-code` | ✅ | Auto-detect AppHost, no prompts |
| `-e <name>` | ✅ | Environment name (non-interactive) |
| `--no-prompt` | Optional | Skip all confirmations |

**Why `--from-code` is critical:**
- Without: Prompts "How do you want to initialize?" (needs TTY)
- With: Auto-detects AppHost, no interaction needed
- Essential for agents and CI/CD

## ⛔ After `azd init`: Fix AddParameter Used with WithBuildArg Before Build/Deploy

> **MANDATORY** — After running `azd init --from-code`, but before `azd package`, `azd up`, or any Docker image build/deploy step, scan the AppHost source for `AddParameter` calls that are passed to `WithBuildArg` or `WithBuildSecret`. This pattern triggers an azd bug that causes Docker builds to fail.

.NET Aspire [external parameters](https://aspire.dev/fundamentals/external-parameters/) let apps request values from the deployment environment. Each `AddParameter()` call generates a Bicep parameter in the deployment manifest. However, azd cannot resolve these Bicep parameters during the Docker image build phase, producing the error `parameter infra.parameters.<name> not found`. This bug has been present across all azd versions tested (including 1.24.0).

### Scan for the pattern

**Bash:**
```bash
grep -RIn --include="*.cs" -E "AddParameter|WithBuildArg|WithBuildSecret" <path/to/AppHost>
```

**PowerShell:**
```powershell
Get-ChildItem -Path "<path/to/AppHost>" -Recurse -Filter "*.cs" |
  Select-String -Pattern "AddParameter|WithBuildArg|WithBuildSecret"
```

**Problematic pattern:**
```csharp
// ❌ azd cannot resolve AddParameter values during Docker builds
var goVersion = builder.AddParameter("goversion", "1.25.4", publishValueAsDefault: true);
builder.AddDockerfile("ginapp", "./ginapp")
    .WithBuildArg("GO_VERSION", goVersion);
```

### Fix Option A: Replace AddParameter with a constant (preferred)

For every `AddParameter(name, defaultValue, ...)` whose result is used **only** as a `WithBuildArg` argument, replace it with a `const string` (or `string`) constant:

```csharp
// ✅ Use a constant instead
const string goVersion = "1.25.4";
builder.AddDockerfile("ginapp", "./ginapp")
    .WithBuildArg("GO_VERSION", goVersion);
```

**Why:** This eliminates the parameter from Bicep output entirely, so azd never attempts to resolve it during Docker builds. Use this when the build arg value does not need to vary per deployment environment.

### Fix Option B: Pre-set parameter in azd environment config

If the value must remain an [external parameter](https://aspire.dev/fundamentals/external-parameters/) (e.g., it varies per environment), pre-set it in the azd environment config immediately after `azd init`:

```bash
azd env config set infra.parameters.<name> <value>
```

**Example:**
```bash
azd env config set infra.parameters.goversion 1.25.4
```

**Why:** This writes the parameter value into `.azure/<env>/config.json` so azd can find it during Docker builds without modifying AppHost source code. Use this when the build arg value must be configurable per environment.

> ⚠️ **Do NOT skip this step for container-build projects.** If the AppHost passes an `AddParameter` result to `WithBuildArg`, apply one of these fixes before running `azd up`.

---

## Troubleshooting

### Error: "Could not find infra\main.bicep"

**Cause:** Manual azure.yaml without services section

**Fix:**
1. Delete manual azure.yaml
2. Run `azd init --from-code -e <env-name>`
3. Verify services section exists

### Error: "no default response for prompt"

**Cause:** Missing `--from-code` flag

**Fix:** Always use `--from-code` for Aspire:
```bash
azd init --from-code -e "$ENV_NAME"
```

### Error: "parameter infra.parameters.<name> not found"

**Cause:** The AppHost uses `AddParameter()` as a `WithBuildArg` argument. azd cannot resolve Aspire [external parameters](https://aspire.dev/fundamentals/external-parameters/) during Docker builds, regardless of azd version.

**Example error:**
```
ERROR: building service 'ginapp': parameter infra.parameters.goversion not found
```

**Fix (Option A — preferred):** In the AppHost source, replace the `AddParameter(...)` call with a constant:

```csharp
// ❌ Before (causes the error)
var goVersion = builder.AddParameter("goversion", "1.25.4", publishValueAsDefault: true);
builder.AddDockerfile("ginapp", "./ginapp")
    .WithBuildArg("GO_VERSION", goVersion);

// ✅ After (fix)
const string goVersion = "1.25.4";
builder.AddDockerfile("ginapp", "./ginapp")
    .WithBuildArg("GO_VERSION", goVersion);
```

**Fix (Option B):** Pre-set the parameter in azd environment config:
```bash
azd env config set infra.parameters.goversion 1.25.4
```

### AppHost Not Detected

**Solutions:**
1. Verify: `find . -name "*.AppHost.csproj"`
2. Build: `dotnet build`
3. Check package references in .csproj
4. Run from solution root

### Error: "unsupported resource type" — Custom Aspire Resources

**Symptoms:** `azd init --from-code` fails with `unsupported resource type` for one or more resources in the AppHost (e.g., custom child resources, ClockHand, or other custom Aspire integration types).

**Cause:** The AppHost contains custom Aspire resource types designed for local development tooling only. These resources have no Azure equivalent and are not deployable.

**Resolution:**

1. ⛔ **Stop — do NOT fix this error by modifying source code.** Do not add `.ExcludeFromManifest()` to suppress the error.
2. ⛔ **Do NOT proceed with deployment.**
3. ✅ Inform the user: the application uses custom Aspire resource authoring patterns intended for local tooling, not cloud deployment.
4. ✅ Record a deployment blocker: "AppHost contains custom Aspire resource types (`unsupported resource type`) with no Azure deployment target."

> ⚠️ Adding `.ExcludeFromManifest()` to work around this error violates the application's design intent and may produce an incomplete or incorrect deployment.

## Infrastructure Auto-Generation

| Traditional | Aspire |
|------------|--------|
| Manual infra/main.bicep | Auto-gen from AppHost |
| Define in IaC | Define in C# code |
| Update IaC per service | Add to AppHost |

**How it works:**
1. AppHost defines services in C#
2. `azd provision` analyzes AppHost
3. Generates Bicep automatically
4. Deploys to Azure Container Apps

## Validation Steps

1. **⛔ Fix `AddParameter` used with `WithBuildArg`** — see [Post-Init: Fix AddParameter Used with WithBuildArg](#after-azd-init-fix-addparameter-used-with-withbuildarg-before-builddeploy)
2. Verify azure.yaml has a non-empty services section
3. Do NOT add separate service entries for `AddDockerfile()` resources — Aspire handles container builds at runtime through the AppHost
4. Run `azd package` to validate Docker build succeeds
5. Review generated infra/ (don't modify)

## Next Steps

1. Set subscription: `azd env set AZURE_SUBSCRIPTION_ID <id>`
2. Proceed to **azure-validate**
3. Deploy with **azure-deploy** (`azd up`)

## References

- [.NET Aspire External Parameters](https://aspire.dev/fundamentals/external-parameters/)
- [.NET Aspire Docs](https://learn.microsoft.com/dotnet/aspire/)
- [azd + Aspire](https://learn.microsoft.com/dotnet/aspire/deployment/azure/aca-deployment-azd-in-depth)
- [Samples](https://github.com/dotnet/aspire-samples)
- [Main Guide](../../aspire.md)
- [azure.yaml Schema](azure-yaml.md)
- [Docker Guide](docker.md)