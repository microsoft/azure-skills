<#
.SYNOPSIS
    Checks Copilot app entry and installs Copilot app-specific add-ons.
.DESCRIPTION
    Detects AI_AGENT=github_copilot_app_agent and, only in that environment,
    silently installs Copilot app-specific add-ons. Currently, the add-on is
    microsoft-foundry. Discovery and installation failures are non-blocking.
#>

$ErrorActionPreference = "Stop"

$pluginName = "microsoft-foundry"
$pluginSpec = "microsoft-foundry@awesome-copilot"

function Write-PluginWarning {
    param([string]$Message)
    Write-Output "[WARN] $Message"
}

if ($env:AI_AGENT -ne "github_copilot_app_agent") {
    exit 0
}

if (-not (Get-Command copilot -ErrorAction SilentlyContinue)) {
    Write-PluginWarning "GitHub Copilot CLI is unavailable; skipped $pluginName plugin installation."
    exit 0
}

try {
    $pluginsRaw = (& copilot plugins list --kind plugin --json 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw $pluginsRaw
    }
    $plugins = $pluginsRaw | ConvertFrom-Json -ErrorAction Stop
} catch {
    Write-PluginWarning "Could not inspect installed Copilot plugins: $($_.Exception.Message)"
    exit 0
}

$installed = @($plugins.plugins) |
    Where-Object { $_ -and $_.name -eq $pluginName } |
    Select-Object -First 1

if ($installed) {
    exit 0
}

try {
    $installOutput = (& copilot plugins install $pluginSpec 2>&1) -join "`n"
    $installExit = $LASTEXITCODE
} catch {
    Write-PluginWarning "Could not install ${pluginSpec}: $($_.Exception.Message)"
    exit 0
}

if ($installExit -ne 0) {
    Write-PluginWarning "Could not install ${pluginSpec}: $installOutput"
}

exit 0
