# Deployment Package

### 3e. Get Deployment Package (if needed)

Ideally your project files are in source control and you can redeploy from there. If not, you can fetch the active package directly from the source app.

#### Check WEBSITE_RUN_FROM_PACKAGE

**Bash:**

```bash
UPGRADE_DIR=<UPGRADE_DIR>
runFromPackage=$(az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='WEBSITE_RUN_FROM_PACKAGE'].value | [0]" -o tsv)
if [[ "$runFromPackage" =~ ^https:// ]]; then
    curl --fail --location --silent --show-error --output "$UPGRADE_DIR/source-package.zip" "$runFromPackage"
    echo "Downloaded the remote deployment package without displaying its URL."
elif [[ "$runFromPackage" == "1" ]]; then
    echo "The package is stored in the app content share."
else
    echo "The app is not configured for run-from-package."
fi
unset runFromPackage
```

**PowerShell 7:**

```powershell
$runFromPackage = $null
try {
    $upgradeDir = '<UPGRADE_DIR>'
    $runFromPackage = az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='WEBSITE_RUN_FROM_PACKAGE'].value | [0]" -o tsv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to read WEBSITE_RUN_FROM_PACKAGE.' }
    $runFromPackage = ([string]$runFromPackage).Trim()
    if ($runFromPackage -match '^https://') {
        Invoke-WebRequest -Uri $runFromPackage -OutFile (Join-Path $upgradeDir 'source-package.zip') -ErrorAction Stop
        Write-Output 'Downloaded the remote deployment package without displaying its URL.'
    }
    elseif ($runFromPackage -eq '1') {
        Write-Output 'The package is stored in the app content share.'
    }
    else {
        Write-Output 'The app is not configured for run-from-package.'
    }
}
finally {
    $runFromPackage = $null
}
```

Interpret the classification:

- **Remote package downloaded** → use `<UPGRADE_DIR>/source-package.zip` in Step 5. Skip the rest of this section.
- **`1`** → the package lives in the app's content file share. Continue below.
- **Empty** → not run-from-package. Either redeploy from source or capture the project files via Kudu (`https://<APP_NAME>.scm.azurewebsites.net`); package retrieval steps below do not apply.

#### Download the package from the content file share

> 🔒 **Security**: `AzureWebJobsStorage` contains the storage account key. Keep it out of command arguments and output by using the Azure CLI's `AZURE_STORAGE_CONNECTION_STRING` environment variable in a scoped block. The cleanup below runs on success or failure.
>
> ⚠️ **Skill instruction**: Do NOT request the value of `AzureWebJobsStorage`, `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING`, or any other connection string from the user. The commands below get them automatically without exposing them.

Get the content share name (not a secret — safe to display):

```bash
az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='WEBSITE_CONTENTSHARE'].value" -o tsv
```

Save the output as `<CONTENT_SHARE>` for the commands below.

> 📁 The download commands below write to `<UPGRADE_DIR>` (default: `.azure-upgrade/<source-app-name>/`). See [Artifact Output Policy](../../../../../global-rules.md#artifact-output-policy). Resolve `<UPGRADE_DIR>` once at session start and create the directory before running these commands.

Download the pointer file and active package in one scoped block. The package filename is not secret and is printed so it can be reused as `<PACKAGE_NAME>` in Step 5.

**Bash:**

```bash
(
  set -e
  trap 'unset AZURE_STORAGE_CONNECTION_STRING' EXIT
  export AZURE_STORAGE_CONNECTION_STRING=$(az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='AzureWebJobsStorage'].value" -o tsv)
  az storage file download --share-name <CONTENT_SHARE> --path data/SitePackages/packagename.txt --dest <UPGRADE_DIR> --no-progress --output none
  PACKAGE_NAME=$(cat <UPGRADE_DIR>/packagename.txt)
  az storage file download --share-name <CONTENT_SHARE> --path "data/SitePackages/$PACKAGE_NAME" --dest <UPGRADE_DIR> --no-progress --output none
  rm <UPGRADE_DIR>/packagename.txt
  printf 'Downloaded package: %s\n' "$PACKAGE_NAME"
)
```

**PowerShell 7:**

```powershell
$previousConnectionString = $env:AZURE_STORAGE_CONNECTION_STRING
try {
    $env:AZURE_STORAGE_CONNECTION_STRING = az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='AzureWebJobsStorage'].value" -o tsv
    if ([string]::IsNullOrWhiteSpace($env:AZURE_STORAGE_CONNECTION_STRING)) { throw 'AzureWebJobsStorage was not found.' }
    az storage file download --share-name <CONTENT_SHARE> --path data/SitePackages/packagename.txt --dest <UPGRADE_DIR> --no-progress --output none
    if ($LASTEXITCODE -ne 0) { throw 'Failed to download packagename.txt.' }
    $packageName = (Get-Content <UPGRADE_DIR>/packagename.txt -Raw).Trim()
    az storage file download --share-name <CONTENT_SHARE> --path "data/SitePackages/$packageName" --dest <UPGRADE_DIR> --no-progress --output none
    if ($LASTEXITCODE -ne 0) { throw 'Failed to download the deployment package.' }
    Remove-Item <UPGRADE_DIR>/packagename.txt
    Write-Output "Downloaded package: $packageName"
}
finally {
    $env:AZURE_STORAGE_CONNECTION_STRING = $previousConnectionString
    $previousConnectionString = $null
}
```

> 💡 The package is a regular `.zip` file — deploy it to the new Flex Consumption app with `az functionapp deployment source config-zip --src <PACKAGE_NAME>` in Step 5. (Linux Consumption uses a different format — `squashfs` in the `scm-releases` blob container — that pattern does NOT apply here.)
>
> 💡 If your storage account is configured for Entra-ID-only auth and the connection string lookup fails, retrieve the account name with `az functionapp show --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "storageAccount" -o tsv` and re-run the file commands with `--account-name <NAME> --auth-mode login` (requires `Storage File Data Privileged Reader` on the share).

---
