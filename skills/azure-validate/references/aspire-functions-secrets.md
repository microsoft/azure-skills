# Aspire + Azure Functions: Secret Storage Validation

> ⚠️ **Pre-provisioning check** — Run this BEFORE `azd provision`.

## When This Applies

This check is required when **all** of these are true:

| Condition | How to detect |
|-----------|--------------|
| .NET Aspire project | `*.AppHost.csproj` exists or `Aspire.Hosting` package reference |
| Azure Functions component | `AddAzureFunctionsProject` call in `AppHost.cs` or `Program.cs` |
| Identity-based storage | `WithHostStorage` call (Aspire default) |

## Detection

Search for `AddAzureFunctionsProject` in the AppHost source file(s):

```bash
grep -rn "AddAzureFunctionsProject" . --include="*.cs"
```

**PowerShell:**
```powershell
Get-ChildItem -Recurse -Filter "*.cs" | Select-String "AddAzureFunctionsProject" -List
```

If found, check whether `AzureWebJobsSecretStorageType` is already configured in those same file(s):

```bash
# Check only the AppHost file(s) that contain AddAzureFunctionsProject
find . -name "*.cs" -path "*AppHost*" -print0 | xargs -0 grep -l "AddAzureFunctionsProject" 2>/dev/null | xargs grep -l "AzureWebJobsSecretStorageType"
```

**PowerShell:**
```powershell
Get-ChildItem -Recurse -Filter "*.cs" |
  Where-Object { $_.FullName -match "AppHost" } |
  Select-String "AddAzureFunctionsProject" -List |
  ForEach-Object { Select-String "AzureWebJobsSecretStorageType" -Path $_.Path }
```

**If `AddAzureFunctionsProject` is present but `AzureWebJobsSecretStorageType` is NOT configured in the same file → fix is required.**

## Fix

Add `.WithEnvironment("AzureWebJobsSecretStorageType", "Files")` to the Azure Functions project builder chain in the AppHost source file that contains the `AddAzureFunctionsProject` call (often `Program.cs` in the `*.AppHost` project).

### Before

```csharp
var functions = builder.AddAzureFunctionsProject<Projects.MyFunctions>("functions")
    .WithHostStorage(storage)
    .WithReference(queues);
```

### After

```csharp
var functions = builder.AddAzureFunctionsProject<Projects.MyFunctions>("functions")
    .WithHostStorage(storage)
    .WithEnvironment("AzureWebJobsSecretStorageType", "Files")
    .WithReference(queues);
```

> 💡 **Tip:** Place `.WithEnvironment(...)` immediately after `.WithHostStorage(...)` for clarity.

## Why This Is Required

Azure Functions needs storage for managing host secrets/keys (function keys, host keys, master key). By default, it stores them as blobs in the `AzureWebJobsStorage` account.

When Aspire configures identity-based storage access (via `WithHostStorage`), it sets URI-based environment variables like `AzureWebJobsStorage__blobServiceUri` instead of a connection string. The Functions runtime's secret manager does **not** support these identity-based URIs — it requires either a connection string or SAS token.

Setting `AzureWebJobsSecretStorageType=Files` switches the Functions host to file-system-based key storage, bypassing the blob storage dependency for secrets.

## Error Without This Setting

```
System.InvalidOperationException: Secret initialization from Blob storage failed
due to missing both an Azure Storage connection string and a SAS connection URI.
For Blob Storage, please provide at least one of these.
```

## When This Check Does NOT Apply

| Scenario | Why |
|----------|-----|
| Aspire project without Azure Functions | No Functions secret manager involved |
| Standalone Azure Functions (not Aspire) | Uses connection string by default |
| Functions with explicit connection string | `AzureWebJobsStorage` is a full connection string, not identity-based |
| `AzureWebJobsSecretStorageType` already set | Configuration is already present |
