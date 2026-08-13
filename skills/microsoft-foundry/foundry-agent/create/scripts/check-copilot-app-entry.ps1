<#
.SYNOPSIS
    Checks Copilot app entry and reports whether its Foundry plugin is installed.
.DESCRIPTION
    Detects AI_AGENT=github_copilot_app_agent, locates either a PATH-visible
    Copilot CLI or the CLI bundled by github-copilot-sdk, and inspects the
    microsoft-foundry plugin. This script never installs the plugin.

    Output lines are prefixed with [OK], [WARN], or [ACTION].
    Exit code is 1 only when plugin installation is required; otherwise 0.
#>

$ErrorActionPreference = "Stop"

$pluginName = "microsoft-foundry"
$pluginSpec = "microsoft-foundry@awesome-copilot"

function Note-Ok     { param([string]$Message) Write-Output "[OK] $Message" }
function Note-Warn   { param([string]$Message) Write-Output "[WARN] $Message" }
function Note-Action { param([string]$Message) Write-Output "[ACTION] $Message" }

function Get-HighestVersionCopilotCli {
    param(
        [string]$Root,
        [string]$ExecutableName
    )

    if (-not $Root -or -not (Test-Path -LiteralPath $Root -PathType Container)) {
        return $null
    }

    $bestPath = $null
    $bestKey = $null
    foreach ($directory in Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue) {
        if ($directory.Name -notmatch '^(\d+)\.(\d+)\.(\d+)(?:-(\d+))?$') {
            continue
        }

        $suffix = if ($Matches[4]) { [long]$Matches[4] } else { [long]::MaxValue }
        $key = @([long]$Matches[1], [long]$Matches[2], [long]$Matches[3], $suffix)
        $candidate = Join-Path $directory.FullName $ExecutableName
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }

        $isNewer = ($null -eq $bestKey)
        if (-not $isNewer) {
            for ($index = 0; $index -lt $key.Count; $index++) {
                if ($key[$index] -gt $bestKey[$index]) {
                    $isNewer = $true
                    break
                }
                if ($key[$index] -lt $bestKey[$index]) {
                    break
                }
            }
        }

        if ($isNewer) {
            $bestPath = $candidate
            $bestKey = $key
        }
    }

    return $bestPath
}

function Find-CopilotCli {
    $pathCommand = Get-Command copilot -CommandType Application,ExternalScript -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($pathCommand) {
        if ($pathCommand.Path) { return $pathCommand.Path }
        if ($pathCommand.Source) { return $pathCommand.Source }
    }

    if ($env:COPILOT_CLI_PATH -and (Test-Path -LiteralPath $env:COPILOT_CLI_PATH -PathType Leaf)) {
        return $env:COPILOT_CLI_PATH
    }

    $isWindowsPlatform = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
        [System.Runtime.InteropServices.OSPlatform]::Windows)
    $isMacPlatform = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
        [System.Runtime.InteropServices.OSPlatform]::OSX)
    $executableName = if ($isWindowsPlatform) { "copilot.exe" } else { "copilot" }

    if ($isWindowsPlatform) {
        $dataRoot = if ($env:LOCALAPPDATA) {
            Join-Path $env:LOCALAPPDATA "github-copilot-sdk\cli"
        } else {
            $null
        }
        $cacheRoot = $dataRoot
    } elseif ($isMacPlatform) {
        $dataRoot = Join-Path $HOME "Library/Application Support/github-copilot-sdk/cli"
        $cacheRoot = Join-Path $HOME "Library/Caches/github-copilot-sdk/cli"
    } else {
        $dataBase = if ($env:XDG_DATA_HOME) { $env:XDG_DATA_HOME } else { Join-Path $HOME ".local/share" }
        $dataRoot = Join-Path $dataBase "github-copilot-sdk/cli"
        $cacheBase = if ($env:XDG_CACHE_HOME -and [IO.Path]::IsPathFullyQualified($env:XDG_CACHE_HOME)) {
            $env:XDG_CACHE_HOME
        } else {
            Join-Path $HOME ".cache"
        }
        $cacheRoot = Join-Path $cacheBase "github-copilot-sdk/cli"
    }

    $appBundledCli = Get-HighestVersionCopilotCli -Root $dataRoot -ExecutableName $executableName
    if ($appBundledCli) {
        return $appBundledCli
    }

    if ($env:COPILOT_CLI_EXTRACT_DIR) {
        $extractedCli = Join-Path $env:COPILOT_CLI_EXTRACT_DIR $executableName
        if (Test-Path -LiteralPath $extractedCli -PathType Leaf) {
            return $extractedCli
        }
    }

    return Get-HighestVersionCopilotCli -Root $cacheRoot -ExecutableName $executableName
}

if ($env:AI_AGENT -ne "github_copilot_app_agent") {
    Note-Ok "GitHub Copilot app not detected; no plugin check needed."
    exit 0
}

$copilotCli = Find-CopilotCli
if (-not $copilotCli) {
    Note-Warn "Could not locate the GitHub Copilot CLI on PATH or in github-copilot-sdk data/cache locations; could not inspect the $pluginName plugin."
    exit 0
}

try {
    # External PowerShell command shims do not set $LASTEXITCODE on success.
    $global:LASTEXITCODE = 0
    $pluginsRaw = (& $copilotCli plugins list --kind plugin --json 2>&1) -join "`n"
    $pluginsExitCode = $LASTEXITCODE
    if ($pluginsExitCode -ne 0) {
        throw $pluginsRaw
    }
    $plugins = $pluginsRaw | ConvertFrom-Json -ErrorAction Stop
} catch {
    Note-Warn "Could not inspect installed Copilot plugins: $($_.Exception.Message)"
    exit 0
}

$installed = @($plugins.plugins) |
    Where-Object { $_ -and $_.name -eq $pluginName } |
    Select-Object -First 1

if ($installed) {
    Note-Ok "Copilot plugin '$pluginName' is installed."
    exit 0
}

$quotedCli = "'" + $copilotCli.Replace("'", "''") + "'"
Note-Action "Copilot plugin '$pluginName' is missing. Run: & $quotedCli plugins install $pluginSpec"
exit 1
