<#
.SYNOPSIS
    Wraps an idempotent `az ... show || az ... create` pair with silent
    retries against transient ARM frontend errors.
.DESCRIPTION
    Mirrors retry-az-create.sh. Runs the show command first (short-circuits
    a partially-succeeded prior attempt and avoids false NameAlreadyExists
    errors). If show fails, runs create. On transient failure (connection
    resets, 429/502/503/504, timeouts) retries up to 2 times with 5s then
    15s backoff. Non-transient failures surface the original error and
    exit 1.
.PARAMETER ShowCommand
    The full `az ... show ...` command line as a single string.
.PARAMETER CreateCommand
    The full `az ... create ...` command line as a single string.
.EXAMPLE
    .\retry-az-create.ps1 `
        -ShowCommand "az group show -n my-rg --only-show-errors" `
        -CreateCommand "az group create -n my-rg -l eastus2"
.EXAMPLE
    .\retry-az-create.ps1 `
        -ShowCommand "az appservice plan show -n my-plan -g my-rg --only-show-errors" `
        -CreateCommand "az appservice plan create -n my-plan -g my-rg --is-linux --sku P0v3 -l eastus2"
#>
param(
    [Parameter(Mandatory)][string]$ShowCommand,
    [Parameter(Mandatory)][string]$CreateCommand
)

$ErrorActionPreference = "Continue"

$transient = 'Connection reset|Connection aborted|ConnectionError|Read timed out|BadGatewayConnection|ServiceUnavailable|Max retries exceeded|TooManyRequests|\b429\b|\b50[234]\b'
$backoff = @(5, 15)

for ($attempt = 1; $attempt -le 3; $attempt++) {
    # Try `show` silently first; if it fails, try `create`. Capture both
    # stdout and stderr into $err so we can inspect for transient patterns.
    $err = & {
        $script = "$ShowCommand -o none 2>`$null; if (`$LASTEXITCODE -ne 0) { $CreateCommand -o none }"
        & powershell -NoProfile -Command $script 2>&1
    } | Out-String

    if ($LASTEXITCODE -eq 0) {
        exit 0
    }

    if ($err -notmatch $transient) {
        Write-Error $err
        exit 1
    }

    if ($attempt -eq 3) {
        Write-Error $err
        Write-Error "ARM frontend is returning transient errors — please retry in a few minutes."
        exit 1
    }

    Start-Sleep -Seconds $backoff[$attempt - 1]
}
