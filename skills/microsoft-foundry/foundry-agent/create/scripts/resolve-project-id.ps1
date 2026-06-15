<#
.SYNOPSIS
    Resolves a Foundry project ARM resource ID from a Foundry project endpoint.
.DESCRIPTION
    Uses the endpoint only to obtain lookup keys for Azure CLI queries. The
    resource ID printed by this script is always the `id` returned by Azure,
    never a locally constructed ARM resource ID.
.EXAMPLE
    ./resolve-project-id.ps1 -Endpoint "https://my-account.services.ai.azure.com/api/projects/my-project"
.EXAMPLE
    ./resolve-project-id.ps1 -Endpoint "https://my-account.services.ai.azure.com/api/projects/my-project" -Output json
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Endpoint,

    [string]$Subscription,

    [string]$ResourceGroup,

    [string]$AccountName,

    [string]$ProjectName,

    [ValidateSet("id", "json")]
    [string]$Output = "id"
)

$ErrorActionPreference = "Stop"

function Stop-Fatal {
    param([string]$Message)
    [Console]::Error.WriteLine("[ERROR] $Message")
    exit 1
}

function Normalize-Endpoint {
    param([string]$Value)
    if (-not $Value) { return "" }
    return $Value.Trim().TrimEnd("/")
}

function Add-SubscriptionArg {
    param([string[]]$CommandArgs)
    if ($Subscription) {
        return $CommandArgs + @("--subscription", $Subscription)
    }
    return $CommandArgs
}

function Invoke-AzJson {
    param([string[]]$CommandArgs)
    $raw = & az @CommandArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "az $($CommandArgs -join ' ') failed: $($raw -join "`n")"
    }
    if (-not $raw) { return $null }
    return (($raw -join "`n") | ConvertFrom-Json -ErrorAction Stop)
}

function Get-ProjectEndpoints {
    param($Project)
    $values = @()
    if ($Project -and $Project.properties -and $Project.properties.endpoints) {
        foreach ($property in $Project.properties.endpoints.PSObject.Properties) {
            if ($property.Value -is [string] -and $property.Value) {
                $values += (Normalize-Endpoint $property.Value)
            }
        }
    }
    return $values
}

function Endpoint-MatchesProject {
    param($Project, [string]$ExpectedEndpoint)
    foreach ($candidate in (Get-ProjectEndpoints $Project)) {
        if ($candidate -eq $ExpectedEndpoint) {
            return $true
        }
    }
    return $false
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Stop-Fatal "Azure CLI 'az' was not found on PATH."
}

$normalizedEndpoint = Normalize-Endpoint $Endpoint
try {
    $endpointUri = [System.Uri]$normalizedEndpoint
} catch {
    Stop-Fatal "Endpoint is not a valid URI: $Endpoint"
}

if (-not $endpointUri.Scheme.StartsWith("http")) {
    Stop-Fatal "Endpoint must be an http or https URI."
}

if (-not $ProjectName) {
    $segments = @($endpointUri.AbsolutePath.Trim("/").Split("/", [System.StringSplitOptions]::RemoveEmptyEntries))
    for ($i = 0; $i -lt $segments.Count; $i++) {
        if ($segments[$i] -ieq "projects" -and ($i + 1) -lt $segments.Count) {
            $ProjectName = [System.Uri]::UnescapeDataString($segments[$i + 1])
            break
        }
    }
}

if (-not $ProjectName) {
    Stop-Fatal "Could not read the project name from the endpoint path. Re-run with -ProjectName."
}

if (-not $AccountName) {
    $hostParts = @($endpointUri.Host.Split("."))
    if ($hostParts.Count -gt 0 -and $endpointUri.Host.EndsWith(".services.ai.azure.com", [System.StringComparison]::OrdinalIgnoreCase)) {
        $AccountName = $hostParts[0]
    }
}

if (-not $AccountName) {
    Stop-Fatal "Could not read the account name from the endpoint host. Re-run with -AccountName."
}

if (-not $ResourceGroup) {
    try {
        $accounts = Invoke-AzJson (Add-SubscriptionArg @("cognitiveservices", "account", "list", "-o", "json"))
    } catch {
        Stop-Fatal $_.Exception.Message
    }

    $matches = @($accounts | Where-Object {
        ($_.name -ieq $AccountName) -or
        ($_.properties.customSubDomainName -ieq $AccountName)
    })

    if ($matches.Count -eq 0) {
        Stop-Fatal "Could not find a Cognitive Services account matching '$AccountName'. Re-run with -ResourceGroup and -AccountName if the endpoint uses a custom host."
    }

    if ($matches.Count -gt 1) {
        $choices = ($matches | ForEach-Object { "$($_.resourceGroup)/$($_.name)" }) -join ", "
        Stop-Fatal "Multiple accounts matched '$AccountName': $choices. Re-run with -ResourceGroup."
    }

    $ResourceGroup = $matches[0].resourceGroup
    $AccountName = $matches[0].name
}

$project = $null
try {
    $project = Invoke-AzJson (Add-SubscriptionArg @(
        "cognitiveservices", "account", "project", "show",
        "-g", $ResourceGroup,
        "-n", $AccountName,
        "--project-name", $ProjectName,
        "-o", "json"
    ))
} catch {
    try {
        $projects = Invoke-AzJson (Add-SubscriptionArg @(
            "cognitiveservices", "account", "project", "list",
            "-g", $ResourceGroup,
            "-n", $AccountName,
            "-o", "json"
        ))
        $project = @($projects | Where-Object { Endpoint-MatchesProject $_ $normalizedEndpoint }) | Select-Object -First 1
    } catch {
        Stop-Fatal $_.Exception.Message
    }
}

if (-not $project) {
    Stop-Fatal "Could not resolve a Foundry project for endpoint '$normalizedEndpoint'."
}

$projectEndpoints = @(Get-ProjectEndpoints $project)
if ($projectEndpoints.Count -gt 0 -and -not (Endpoint-MatchesProject $project $normalizedEndpoint)) {
    Stop-Fatal "Resolved project endpoint metadata did not match '$normalizedEndpoint'."
}

if (-not $project.id) {
    Stop-Fatal "Azure returned a project object without an id."
}

if ($Output -eq "json") {
    [ordered]@{
        id = $project.id
        endpoint = if ($projectEndpoints.Count -gt 0) { $projectEndpoints[0] } else { $normalizedEndpoint }
        resourceGroup = $ResourceGroup
        accountName = $AccountName
        projectName = $ProjectName
    } | ConvertTo-Json -Depth 5
} else {
    Write-Output $project.id
}
