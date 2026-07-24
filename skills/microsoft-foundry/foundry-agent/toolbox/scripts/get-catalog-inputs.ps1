<#
.SYNOPSIS
  Discover catalog inputs for Foundry catalog MCP connections and classify which
  auth types each matching connector supports: MANAGED OAUTH and/or USER ENTRA TOKEN.

.DESCRIPTION
  For each match prints:
    - toolEntityId    -> azd ai connection create --metadata toolEntityId=...
    - serverUrl       -> azd ai connection create --target ...   (best-effort; see note)
    - managedOAuth    -> true when Foundry can broker the connector's OAuth app
    - connectorName   -> (managed only) the brokered app for --connector-name (e.g. foundrygithubmcp)
    - userEntraToken  -> true when the tile forwards the caller's Entra identity
    - audience        -> (user-entra-token only) the value --audience needs
    - scopes          -> OAuth scopes advertised by the tool

  Queries the MCP registry (registry-prod-bl). The MCP catalog lives only in
  eastus; the public connectors-registry-prod-bl holds Logic Apps connectors
  (not MCP tools), so it is not queried.

  HOW AUTH TYPES ARE DETECTED (mirrors the portal, verified against
  app/src/components/tools/Config/ToolConfigFields.tsx + transformTools.tsx): the
  asset-gallery entity's `properties` carry the signals the portal keys off:
    * host = "remotes"       when kind == "mcp" and properties.remotes is non-empty.
    * x-ms-connector-name    the Foundry-brokered OAuth app (e.g. "foundrygithubmcp").
    * x-ms-auth-schemas      scheme keys (oauth2 / managedidentity / agentidentity);
                             often EMPTY even for OAuth tiles.
    * x-ms-security-schemes  the OpenAPI-style scheme block (declares oauth2, scopes).
    * x-ms-audience          the resource the forwarded user token is scoped to.
  MANAGED OAUTH (portal supportsManagedOAuth) = has x-ms-connector-name OR
    x-ms-auth-schemas contains "oauth2". Foundry brokers the app; the config dialog
    needs connector-name + toolEntityId and does NOT ask for an audience. (github/
    vercel qualify via connector-name; sentinel/foundry-mcp via oauth2.) work_iq /
    fabric_iq are hard-coded managed.
  USER ENTRA TOKEN (Microsoft Entra -> Agent User Impersonation) = NO brokered
    connector-name, but the tile declares an oauth2 scheme AND an x-ms-audience, so
    the caller identity is forwarded. The config dialog REQUIRES that audience.
    (work_iq, foundry-mcp, sentinel qualify.) A tile can support BOTH.

  NOTE on serverUrl: remotes[].url is often null in the index (verified for
  github). When empty, supply the connector's documented MCP endpoint as
  --target (e.g. github Copilot -> https://api.githubcopilot.com/mcp).

.EXAMPLE
  ./get-catalog-inputs.ps1                    # list ALL MCP tiles
  ./get-catalog-inputs.ps1 -ManagedOAuth      # list all managed-OAuth tiles
  ./get-catalog-inputs.ps1 -UserEntraToken    # list all user-entra-token tiles
  ./get-catalog-inputs.ps1 github             # narrow by name substring

.NOTES
  Requires: Az CLI (logged in). Uses an ARM bearer token.
  The Name substring is OPTIONAL — omit it to list every MCP tile.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $false, Position = 0)]
  [string] $Name = '',
  [switch] $ManagedOAuth,
  [switch] $UserEntraToken
)

$ErrorActionPreference = 'Stop'
$gallery = 'https://eastus.api.azureml.ms/asset-gallery/v1.0/tools'
$token = az account get-access-token --resource 'https://management.azure.com' --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; 'Content-Type' = 'application/json' }
$hardcodedManaged = @('work_iq', 'fabric_iq')

# Fetch one page of the MCP registry with NO name filter. This matters: adding an
# `annotations/name contains` filter makes the index return a THIN projection (only
# timestamps) that omits x-ms-auth-schemas / kind / remotes — the fields we classify
# on. Fetching unfiltered returns full properties; we match $Name client-side.
function Get-RegistryPage([string] $ContinuationToken) {
  $bodyObj = @{
    freeTextSearch = '*'
    filters        = @(
      @{ field = 'entityContainerId'; operator = 'eq'; values = @('registry-prod-bl') },
      @{ field = 'type';              operator = 'eq'; values = @('tools') }
    )
    pageSize       = 100
  }
  if ($ContinuationToken) { $bodyObj['continuationToken'] = $ContinuationToken }
  $body = $bodyObj | ConvertTo-Json -Depth 6
  # Invoke-WebRequest + ConvertFrom-Json is more reliable than Invoke-RestMethod
  # here: the deeply-nested catalog payload can bind `.value` to $null under IRM.
  # -AsHashtable is required — the payload has a property with an empty-string name.
  $resp = Invoke-WebRequest -Method Post -Uri $gallery -Headers $headers `
    -ContentType 'application/json' -Body $body -UseBasicParsing
  $resp.Content | ConvertFrom-Json -Depth 40 -AsHashtable
}

# First OAuth scope key from x-ms-security-schemes (the audience fallback).
function Get-FirstScopeKey($props) {
  $ss = $props['x-ms-security-schemes']
  if ($ss -is [string]) { try { $ss = $ss | ConvertFrom-Json -AsHashtable } catch { $ss = @{} } }
  if ($ss -is [System.Collections.IDictionary]) {
    foreach ($v in $ss.Values) {
      if (($v -is [System.Collections.IDictionary]) -and $v['type'] -eq 'oauth2') {
        $flows = $v['flows']; if (-not ($flows -is [System.Collections.IDictionary])) { continue }
        $ac = $flows['authorizationCode']; if (-not ($ac -is [System.Collections.IDictionary])) { continue }
        $scopes = $ac['scopes']
        if (($scopes -is [System.Collections.IDictionary]) -and $scopes.Count) { return ($scopes.Keys | Select-Object -First 1) }
      }
    }
  }
  ''
}

function Get-AllScopes($props) {
  $ss = $props['x-ms-security-schemes']
  if ($ss -is [string]) { try { $ss = $ss | ConvertFrom-Json -AsHashtable } catch { $ss = @{} } }
  $out = @()
  if ($ss -is [System.Collections.IDictionary]) {
    foreach ($v in $ss.Values) {
      if (($v -is [System.Collections.IDictionary]) -and $v['type'] -eq 'oauth2') {
        $flows = $v['flows']; if (-not ($flows -is [System.Collections.IDictionary])) { continue }
        $ac = $flows['authorizationCode']; if (-not ($ac -is [System.Collections.IDictionary])) { continue }
        $scopes = $ac['scopes']
        if ($scopes -is [System.Collections.IDictionary]) { $out += $scopes.Keys }
      }
    }
  }
  $out -join ','
}

# True if x-ms-security-schemes declares an oauth2 scheme (the tile can do OAuth).
function Get-HasOAuth2Scheme($props) {
  $ss = $props['x-ms-security-schemes']
  if ($ss -is [string]) { try { $ss = $ss | ConvertFrom-Json -AsHashtable } catch { $ss = @{} } }
  if ($ss -is [System.Collections.IDictionary]) {
    foreach ($v in $ss.Values) { if (($v -is [System.Collections.IDictionary]) -and $v['type'] -eq 'oauth2') { return $true } }
  }
  $false
}

Write-Host "# Querying the MCP registry (registry-prod-bl) for '$Name'..." -ForegroundColor Cyan
$rows = @()
$ct = $null
for ($i = 0; $i -lt 10; $i++) {   # safety cap: 10 pages * 100 = 1000 entities
  $page = Get-RegistryPage $ct
  if (-not $page) { break }
  $val = $page['value']
  if ($val) { $rows += $val }
  $ct = $page['continuationToken']
  if (-not $ct) { break }
}

$needle = $Name.ToLower()
$seen = [ordered]@{}
foreach ($r in $rows) {
  $eid = $r['entityId']
  if (-not $eid) { continue }
  $props = $r['properties']; if (-not $props) { $props = @{} }
  $cp = $props['customProperties']; if (-not $cp) { $cp = @{} }
  $ann = $r['annotations']; if (-not $ann) { $ann = @{} }
  $conn = if ($eid -match 'objectId/([^/]+)') { $Matches[1] } else { '' }
  $toolId = if ($cp['id']) { $cp['id'] } else { $conn }
  $title = $props['title']
  $name = if ($ann['name']) { $ann['name'] } elseif ($title) { $title } elseif ($r['name']) { $r['name'] } else { $conn }

  # Client-side name match (the request carries no name filter — see Get-RegistryPage).
  if ($needle -and -not ("$name $conn $title $toolId".ToLower().Contains($needle))) { continue }

  $remotes = $props['remotes']
  $url = if ($remotes) { $remotes[0]['url'] } else { '' }
  $toolHost = if ($props['kind'] -eq 'mcp' -and $remotes) { 'remotes' } else { $cp['type'] }

  $schemes = $props['x-ms-auth-schemas']
  if ($schemes -is [string]) { try { $schemes = $schemes | ConvertFrom-Json } catch { $schemes = @($schemes) } }
  $low = @(); if ($schemes) { $low = @($schemes | ForEach-Object { "$_".ToLower() }) }

  $connectorName = $props['x-ms-connector-name']   # Foundry-brokered app, e.g. 'foundrygithubmcp'
  $audience = $props['x-ms-audience']
  $oauth2Scheme = Get-HasOAuth2Scheme $props

  # Auth classification (mutually exclusive — one type per tile):
  #   user-entra-token = 'oauth2' listed in x-ms-auth-schemas (foundry-mcp, M365
  #     frontier, dataverse, sentinel, fabric) — the portal commits UserEntraToken.
  #   managed OAuth = has an x-ms-connector-name (github/vercel) OR an oauth2
  #     security-scheme with NO managedidentity/agentidentity declared in
  #     x-ms-auth-schemas (work_iq, yutori, oracle...). work_iq / fabric_iq hard-coded.
  #   AGENT IDENTITY (excluded here) = x-ms-auth-schemas lists managedidentity or
  #     agentidentity (Azure Language, Azure Managed Grafana, Azure AI Search) —
  #     see tool-mcp-agent-identity.md. Key-auth / no-auth tiles are also excluded.
  $isRemote = ($toolHost -eq 'remotes')
  $hasMiAgent = ($low -contains 'managedidentity') -or ($low -contains 'agentidentity')
  $entra = ($isRemote -and ($low -contains 'oauth2'))
  $managed = (($isRemote -and ([bool]$connectorName -or ($oauth2Scheme -and -not $hasMiAgent))) -or ($hardcodedManaged -contains "$toolId".ToLower())) -and (-not $entra)

  if (-not $audience) { $audience = Get-FirstScopeKey $props }

  # Dedup on objectId across versions/pages; prefer the richest record
  # (a rich projection has auth schemes / connector-name; a thin one is empty).
  $key = if ($conn) { $conn } else { $eid }
  $schemeStr = ($low -join ',')
  # Dedup on objectId across versions/pages; prefer the record that actually classified
  # (managed/entra) or carries auth signals — a thin projection has none of these.
  $newRich = $managed -or $entra -or [bool]$schemeStr -or [bool]$connectorName -or [bool]$audience
  if ($seen.Contains($key)) {
    $old = $seen[$key]
    $oldRich = $old.managed -or $old.entra -or [bool]$old.schemes -or [bool]$old.connector_name -or [bool]$old.audience
    if ($oldRich -and -not $newRich) { continue }
  }
  $seen[$key] = [pscustomobject]@{
    name = $name; title = $title; conn = $conn; eid = $eid; url = $url
    schemes = $schemeStr; connector_name = $connectorName
    managed = $managed; entra = $entra
    audience = $audience; scopes = (Get-AllScopes $props)
  }
}

$count = 0
Write-Host ''
foreach ($row in $seen.Values) {
  if (-not $row.conn) { continue }
  if ($ManagedOAuth   -and -not $row.managed) { continue }
  if ($UserEntraToken -and -not $row.entra)   { continue }
  $count++
  Write-Host ("  name           : {0}" -f $row.name)
  $dn = if ($row.title) { $row.title } else { '<none>' }
  Write-Host ("  displayName    : {0}" -f $dn)
  Write-Host ("  toolEntityId   : {0}" -f $row.eid)
  $u = if ($row.url) { $row.url } else { '<empty — use documented MCP URL>' }
  Write-Host ("  serverUrl      : {0}" -f $u)
  $sch = if ($row.schemes) { $row.schemes } else { '<none>' }
  Write-Host ("  authSchemes    : {0}" -f $sch)
  Write-Host ("  managedOAuth   : {0}" -f $row.managed.ToString().ToLower())
  if ($row.managed) {
    # --connector-name for the managed-OAuth connection = the Foundry-brokered app
    # name (x-ms-connector-name, e.g. 'foundrygithubmcp'), NOT the toolEntityId objectId.
    $cn = if ($row.connector_name) { $row.connector_name } else { '<none — this tile has no brokered connector; use user-entra-token>' }
    Write-Host ("  connectorName  : {0}" -f $cn)
  }
  Write-Host ("  userEntraToken : {0}" -f $row.entra.ToString().ToLower())
  if ($row.entra) {
    $aud = if ($row.audience) { $row.audience } else { '<derive from OAuth scope key>' }
    Write-Host ("  audience       : {0}" -f $aud)
  }
  if ($row.managed -and $row.scopes) {
    Write-Host ("  scopes         : {0}" -f $row.scopes)
  }
  Write-Host ''
}
$suffix = if ($ManagedOAuth) { ' supporting managed OAuth' } elseif ($UserEntraToken) { ' supporting user-entra-token' } else { '' }
Write-Host "# $count connector(s)$suffix."

Write-Host @'

# Managed OAuth (config dialog does NOT ask for an audience):
#   azd ai connection create <name> `
#     --kind remote-tool --auth-type oauth2 `
#     --target <serverUrl-or-documented-MCP-URL> `
#     --connector-name <connectorName> `
#     --metadata type=catalog_MCP `
#     --metadata toolEntityId=<toolEntityId> `
#     --project-endpoint "$env:FOUNDRY_PROJECT_ENDPOINT"
#
# User Entra token (config dialog REQUIRES an audience):
#   azd ai connection create <name> `
#     --kind remote-tool --auth-type user-entra-token `
#     --target <serverUrl-or-documented-MCP-URL> `
#     --audience <audience-from-report> `
#     --project-endpoint "$env:FOUNDRY_PROJECT_ENDPOINT"
'@ -ForegroundColor DarkGray
