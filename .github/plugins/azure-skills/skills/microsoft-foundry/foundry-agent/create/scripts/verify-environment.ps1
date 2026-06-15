<#
.SYNOPSIS
    Verifies the local environment for creating a hosted Foundry agent with `azd ai`.
.DESCRIPTION
    Runs all the read-only checks in one pass and prints a single concise summary,
    so the agent does not have to run (and reason over) each azd command separately.

    Output lines are prefixed with [OK], [WARN], or [ACTION].
    Exit code is 0 when no blocking actions remain, 1 when at least one [ACTION] is required.
.EXAMPLE
    ./verify-environment.ps1
#>

$ErrorActionPreference = "Stop"
$actionRequired = $false

function Note-Ok     { param([string]$m) Write-Output "[OK] $m" }
function Note-Warn   { param([string]$m) Write-Output "[WARN] $m" }
function Note-Action { param([string]$m) Write-Output "[ACTION] $m"; $script:actionRequired = $true }

function Get-AzdJson {
    param([string[]]$AzdArgs)
    try {
        $raw = & azd @AzdArgs 2>$null
        if (-not $raw) { return $null }
        return ($raw | ConvertFrom-Json -ErrorAction Stop)
    } catch {
        return $null
    }
}

# Refresh PATH to pick up recently-installed tools (e.g. azd installed in same session)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# 1. azd present + version
# Check PATH first, then probe common install locations (winget, MSI, chocolatey)
if (-not (Get-Command azd -ErrorAction SilentlyContinue)) {
    $azdFallbackPaths = @(
        "$env:LOCALAPPDATA\Programs\Azure Dev CLI"
        "$env:ProgramFiles\Azure Dev CLI"
        "${env:ProgramFiles(x86)}\Azure Dev CLI"
        "$env:USERPROFILE\.azd\bin"
    )
    $found = $false
    foreach ($dir in $azdFallbackPaths) {
        if (Test-Path "$dir\azd.exe") {
            $env:Path = "$dir;$env:Path"
            Note-Warn "azd found at '$dir' but was not on PATH. Added automatically for this session."
            $found = $true
            break
        }
    }
    if (-not $found) {
        Note-Action "Azure Developer CLI (azd) is not installed. Install it from https://aka.ms/azd-install, then re-run."
        Write-Output ""
        Write-Output "Summary: azd missing -- cannot continue."
        exit 1
    }
}

$verJson = Get-AzdJson @("version", "--output", "json")
$azdVersion = if ($verJson -and $verJson.azd -and $verJson.azd.version) { $verJson.azd.version } else { "unknown" }
Note-Ok "azd installed (version $azdVersion)."

# 2. Required extensions
$extRaw = (& azd extension list --output json 2>$null) -join "`n"
foreach ($ext in @("azure.ai.agents", "azure.ai.projects")) {
    if ($extRaw -match [regex]::Escape($ext)) {
        Note-Ok "Extension '$ext' is installed."
    } else {
        Note-Action "Extension '$ext' is missing. Run: azd extension install $ext"
    }
}

# 3. Auth status
& azd auth login --check-status *> $null
if ($LASTEXITCODE -eq 0) {
    Note-Ok "Logged in to azd."
} else {
    Note-Action "Not logged in. Ask the user to run 'azd auth login' (it opens a browser; never run it for them)."
}

# 4. Foundry project endpoint (optional at this stage)
# Short-circuit when there's no azd project in cwd: `azd ai project show` / `agent show`
# would just return nothing after a ~3s subprocess each.
if (-not (Test-Path "azure.yaml")) {
    Note-Warn "No Foundry project endpoint set yet. A new project will be created at provision/deploy time, or supply an existing project resource ID."
    Note-Ok "No agent deployed yet. Proceed with create."
} else {
    $projectJson = Get-AzdJson @("ai", "project", "show", "--output", "json")
    $endpoint = $null
    if ($projectJson) {
        foreach ($k in @("endpoint", "projectEndpoint", "aiProjectEndpoint")) {
            if ($projectJson.PSObject.Properties.Name -contains $k -and $projectJson.$k) {
                $endpoint = $projectJson.$k
                break
            }
        }
    }
    if ($endpoint) {
        Note-Ok "Foundry project endpoint configured: $endpoint"
    } else {
        Note-Warn "No Foundry project endpoint set yet. A new project will be created at provision/deploy time, or supply an existing project resource ID."
    }

    # 5. Agent deployment status
    $agentJson = Get-AzdJson @("ai", "agent", "show", "--output", "json")
    if ($agentJson) {
        $status = if ($agentJson.PSObject.Properties.Name -contains "status" -and $agentJson.status) { $agentJson.status } else { "unknown" }
        switch ($status) {
            { $_ -in @("active", "deployed") } { Note-Ok "An agent is already deployed (status: $status). Skip to deploy.md to redeploy, or tools to add a tool." }
            "not_deployed"                     { Note-Ok "No agent deployed yet (status: not_deployed). Proceed with create." }
            default                            { Note-Warn "Agent status: $status." }
        }
    } else {
        Note-Ok "No agent deployed yet. Proceed with create."
    }
}

Write-Output ""
if ($actionRequired) {
    Write-Output "Summary: action required -- resolve the [ACTION] items above before continuing."
    exit 1
} else {
    Write-Output "Summary: environment ready for 'azd ai' hosted-agent creation."
    exit 0
}
