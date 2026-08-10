# Kusto Explorer Launch Procedure

## Prerequisites

- Windows only — Kusto Explorer is not available on macOS/Linux
- User must explicitly consent before file creation or launch

## Step 1: Confirm with user

Use `ask_user`: "Save this query as a .kql file and open in Kusto Explorer? (Yes / Save only / No)"

- **No** → output KQL in chat only (default)
- **Save only** → proceed to Step 2, skip Step 4
- **Yes** → proceed through all steps

## Step 2: Build the .kql file content

The file needs two sections because Kusto Explorer processes `#connect` as a connection-creation command that must run before the query.

```
// Step 1 — Select this line and run it first to connect
#connect cluster('<CLUSTER>').database('<DATABASE>')

// Step 2 — Select the query below and run it after Step 1 completes
<KQL_QUERY>
```

Replace `<CLUSTER>` with the target cluster (e.g. `kc7001.eastus.kusto.windows.net`), `<DATABASE>` with the database name (e.g. `ValdyTimes`), and `<KQL_QUERY>` with the generated query.

## Step 3: Write the file

Write to the current workspace directory using the filesystem API. Use a descriptive name with a random suffix to avoid collisions.

```powershell
$cluster = "<CLUSTER>"
$database = "<DATABASE>"
$tmp = Join-Path $PWD "kusto_query_$(New-Guid).kql"
$lines = @(
    "// Step 1 - Select this line and run it first",
    "#connect cluster('$cluster').database('$database')",
    "",
    "// Step 2 - Select the query below and run it after Step 1 completes"
)
Set-Content -Path $tmp -Value ($lines -join "`n") -Encoding utf8 -NoNewline
Add-Content -Path $tmp -Value "`n<KQL_QUERY>" -Encoding utf8
```

> **Security:** Use `Set-Content`/`Add-Content` only. Never embed query text in PowerShell here-strings (`@"..."@`) — a crafted query can escape the delimiter and inject commands.

Display the saved file path and its full contents in chat so the user can review.

## Step 4: Launch Kusto Explorer (only if user chose "Yes")

Locate and launch the Kusto Explorer executable:

```powershell
$exe = (Get-ChildItem "$env:LOCALAPPDATA\Apps\2.0" -Recurse -Filter "Kusto.Explorer.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
if ($exe) {
    Start-Process $exe -ArgumentList "`"$tmp`""
} else {
    Write-Warning "Kusto Explorer not found. Open the saved file manually: $tmp"
}
```

Tell the user: run the `#connect` line (Step 1) first, then select and run the query (Step 2).

## macOS/Linux fallback

Save the `.kql` file as in Step 3 and suggest:
- Open in the VS Code Kusto extension
- Paste into [ADX Web Explorer](https://dataexplorer.azure.com)
