#!/usr/bin/env pwsh
# Scaffold -> Deploy conformance gate.
# Checks generated IaC against the plan for the semantic defects `az bicep build`
# cannot catch (valid Bicep, wrong values) — the class that causes deploy healing.
#
# Usage:  scaffold-conformance.ps1 -SessionPath <.copilot-azure/sessions/{id}> -InfraPath <infra>
# Output: JSON { passed, failures:[{id,detail,file}] } to stdout.
# Exit:   0 = pass, 1 = one or more BLOCK failures.
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string]$SessionPath,
  [string]$InfraPath = 'infra'
)

$failures = New-Object System.Collections.Generic.List[object]
function Add-Fail($id, $detail, $file) {
  $failures.Add([ordered]@{ id = $id; detail = $detail; file = $file })
}
function Read-Json($p) {
  if (Test-Path $p) { try { return (Get-Content $p -Raw | ConvertFrom-Json) } catch { return $null } }
  return $null
}

# --- Load artifacts (a missing input skips only the checks that need it) ---
$plan = Read-Json (Join-Path $SessionPath 'prepare-plan.json')

$mainPath   = Join-Path $InfraPath 'main.bicep'
$paramsPath = Join-Path $InfraPath 'main.parameters.json'
$mainBicep  = if (Test-Path $mainPath)   { Get-Content $mainPath -Raw }   else { '' }
$paramsRaw  = if (Test-Path $paramsPath) { Get-Content $paramsPath -Raw } else { '' }
$iac = ''
if (Test-Path $InfraPath) {
  $iac = (Get-ChildItem $InfraPath -Recurse -Filter *.bicep -ErrorAction SilentlyContinue |
          ForEach-Object { Get-Content $_.FullName -Raw }) -join "`n"
}

$svcNames = @()
if ($plan -and $plan.services) { $svcNames = @($plan.services | ForEach-Object { $_.name }) }
function Has-Service($re) { return [bool]($svcNames | Where-Object { $_ -match $re }) }

# 1. TAGS-NO-CAMEL — tag keys must be hyphenated, not Bicep camelCase identifiers.
if ($mainBicep -match 'appOnboard(Skill|SessionId)|createdAt:|deployedBy:') {
  Add-Fail 'TAGS-NO-CAMEL' "camelCase tag keys found — use hyphenated ('app-onboard-skill' ...)" 'infra/main.bicep'
}

# 12. DIAG-GATED — we don't scaffold diagnostic-settings; if the generator added one it must be gated behind
#     enableDiagnostics (default false) or removed. Unconditional wiring blocks the first deploy (target/workspace not ready).
#     Match an actual diagnostic MODULE/RESOURCE declaration, not a prose comment mentioning 'diagnostic'.
if ($mainBicep -match 'module\s+\w*[Dd]iagnostic|Microsoft\.Insights/diagnosticSettings' -and $mainBicep -notmatch 'enableDiagnostics') {
  Add-Fail 'DIAG-GATED' 'diagnostic-settings module wired without an enableDiagnostics gate — gate it (module ... = if (enableDiagnostics), default false) or remove it; unconditional wiring blocks the first deploy' 'infra/main.bicep'
}

# 2. NO-PLAINTEXT-SECRET — secrets are @secure() params passed at deploy, never literals.
if ($paramsRaw) {
  try {
    $pj = $paramsRaw | ConvertFrom-Json
    foreach ($k in $pj.parameters.PSObject.Properties.Name) {
      if ($k -match '(?i)password|secret|connstring|connection') {
        $val = $pj.parameters.$k.value
        if ($null -ne $val -and "$val".Trim().Length -gt 0) {
          Add-Fail 'NO-PLAINTEXT-SECRET' "parameter '$k' has a literal value — must be @secure(), passed at deploy" 'infra/main.parameters.json'
        }
      }
    }
  } catch { }
}

# 2b. NO-BICEP-LITERAL-SECRET — secret values must be @secure() params, never quoted literals in Bicep.
#     Property name must end in 'password'/'connectionString' right before ':' (so 'secretName' etc. never match).
if ($iac) {
  foreach ($m in [regex]::Matches($iac, "(?im)\b([A-Za-z]*(?:password|connectionstring))\s*:\s*'([^']+)'")) {
    Add-Fail 'NO-BICEP-LITERAL-SECRET' "property '$($m.Groups[1].Value)' assigned a literal secret in Bicep — use an @secure() param passed at deploy" 'infra/'
  }
  if ($iac -match "(?im):\s*'[^']*(?:Password=|AccountKey=|SharedAccessKey=|://[^:@/\s]+:[^:@/\s]+@)[^']*'") {
    Add-Fail 'NO-BICEP-LITERAL-SECRET' 'quoted literal contains an embedded credential (Password=/AccountKey=/user:pass@) in Bicep — use an @secure() param' 'infra/'
  }
}

# 3. SERVICES-COMPLETE — every planned service maps to a resource type present in the IaC.
$typeMap = [ordered]@{
  'container apps environment'   = 'Microsoft\.App/managedEnvironments'
  'container app'                = 'Microsoft\.App/containerApps'
  'container registry'           = 'Microsoft\.ContainerRegistry/registries'
  'mysql'                        = 'Microsoft\.DBforMySQL/flexibleServers'
  'postgres'                     = 'Microsoft\.DBforPostgreSQL/flexibleServers'
  'key vault'                    = 'Microsoft\.KeyVault/vaults'
  'log analytics'                = 'Microsoft\.OperationalInsights/workspaces'
  'application insights'         = 'Microsoft\.Insights/components'
  'static web app'               = 'Microsoft\.Web/staticSites'
  'app service'                  = 'Microsoft\.Web/sites'
  'functions'                    = 'Microsoft\.Web/sites'
  'sql'                          = 'Microsoft\.Sql/servers'
  'cosmos'                       = 'Microsoft\.DocumentDB/databaseAccounts'
  'redis'                        = 'Microsoft\.Cache/redis'
  'storage'                      = 'Microsoft\.Storage/storageAccounts'
  'service bus'                  = 'Microsoft\.ServiceBus/namespaces'
  'event hub'                    = 'Microsoft\.EventHub/namespaces'
}
if ($iac) {
  foreach ($name in $svcNames) {
    $lc = "$name".ToLower(); $expected = $null
    foreach ($k in $typeMap.Keys) { if ($lc.Contains($k)) { $expected = $typeMap[$k]; break } }
    if ($expected -and ($iac -notmatch $expected)) {
      Add-Fail 'SERVICES-COMPLETE' "planned service '$name' has no matching resource ($expected) in IaC" 'infra/'
    }
  }
}

# --- Managed database checks ---
$hasMysql = Has-Service 'MySQL'
$hasPg    = Has-Service 'PostgreSQL|Postgres'
if (($hasMysql -or $hasPg) -and $iac) {
  # 4. DB-VERSION-MATCH — each server's version must equal its capabilities-verified plan value.
  #    Scope the match to the DB resource block so an unrelated 'version:' elsewhere isn't picked up.
  $dbTypeRe = @{ 'MySQL' = 'Microsoft\.DBforMySQL/flexibleServers'; 'PostgreSQL' = 'Microsoft\.DBforPostgreSQL/flexibleServers' }
  foreach ($svc in ($plan.services | Where-Object { $_.name -match 'MySQL|PostgreSQL' -and $_.version })) {
    $kind = if ($svc.name -match 'MySQL') { 'MySQL' } else { 'PostgreSQL' }
    $m = [regex]::Match($iac, "$($dbTypeRe[$kind])[\s\S]{0,800}?version:\s*'([^']+)'")
    if ($m.Success -and $m.Groups[1].Value -ne $svc.version) {
      Add-Fail 'DB-VERSION-MATCH' "$kind IaC version '$($m.Groups[1].Value)' != plan '$($svc.version)'" 'infra/modules'
    }
  }

  # 5. DB-TLS-ON (MySQL) — require_secure_transport must be enforced.
  if ($hasMysql -and ($iac -notmatch 'require_secure_transport')) {
    Add-Fail 'DB-TLS-ON' 'MySQL module missing require_secure_transport config' 'infra/modules'
  }

  # 6. DB-NAME-PRESENT — the app's named DB must exist in IaC (from prepare-plan.appDbName).
  if ($plan.appDbName -and ($iac -notmatch 'flexibleServers/databases')) {
    Add-Fail 'DB-NAME-PRESENT' "app DB '$($plan.appDbName)' declared but no flexibleServers/databases resource" 'infra/modules'
  }

  # 10. MYSQL-NO-NETWORK-BLOCK (MySQL) — the public-access flow must OMIT the network block.
  #     An empty delegatedSubnetResourceId/privateDnsZoneResourceId is rejected by ARM (LinkedInvalidPropertyId).
  if ($hasMysql -and ($iac -match 'delegatedSubnetResourceId|privateDnsZoneResourceId')) {
    Add-Fail 'MYSQL-NO-NETWORK-BLOCK' 'MySQL module includes a network block (delegatedSubnetResourceId) — omit it for public access; an empty value is rejected by ARM' 'infra/modules'
  }

  # 11. DB-LOGIN-NOT-RESERVED — administratorLogin must not be an Azure-reserved name.
  if ($iac -match "administratorLogin:\s*'(root|admin|administrator|guest|public|sa|azure_superuser|azure_pg_admin)'") {
    Add-Fail 'DB-LOGIN-NOT-RESERVED' "administratorLogin uses a reserved name ('$($Matches[1])') — derive a safe login (e.g. '{project}admin'), never a compose-sourced reserved name" 'infra/modules'
  }
}

# --- Key Vault checks ---
# Gate on the IaC resource (matches the .sh twin and this script's own CA/ACR gating) — NOT the plan
# service name, which misses KV when the plan names the service anything other than 'Key Vault'.
if (($iac -match 'Microsoft\.KeyVault/vaults')) {
  # 7. KV-NO-PURGE — subscription policy rejects enablePurgeProtection:false; omit it entirely.
  if ($iac -match 'enablePurgeProtection') {
    Add-Fail 'KV-NO-PURGE' 'enablePurgeProtection present — omit it (policy may reject false)' 'infra/modules'
  }
  # 8. KV-DEPLOYER-ROLE — deployer needs Key Vault Secrets Officer + a deployerObjectId param.
  $hasOfficer = $iac -match 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
  $hasParam   = ($paramsRaw -match 'deployerObjectId') -or ($iac -match 'deployerObjectId')
  if (-not ($hasOfficer -and $hasParam)) {
    Add-Fail 'KV-DEPLOYER-ROLE' 'missing deployer Key Vault Secrets Officer role and/or deployerObjectId param' 'infra/modules/role-assignments.bicep'
  }
}

# --- Container Apps / ACR checks (deterministic ARM-failure invariants) ---
$hasCA  = $iac -match 'Microsoft\.App/containerApps'
$hasCAE = $iac -match 'Microsoft\.App/managedEnvironments'
$hasAcr = $iac -match 'Microsoft\.ContainerRegistry/registries'
if ($iac) {
  # 13. CAE-APPLOGS — managedEnvironments log config MUST nest under appLogsConfiguration; a bare
  #     top-level logAnalyticsConfiguration fails deploy with ManagedEnvironmentInvalidSchema.
  if ($hasCAE -and ($iac -match 'logAnalyticsConfiguration') -and ($iac -notmatch 'appLogsConfiguration')) {
    Add-Fail 'CAE-APPLOGS' "Container Apps Environment uses a bare logAnalyticsConfiguration — nest it under appLogsConfiguration.destination='log-analytics' (else ManagedEnvironmentInvalidSchema at deploy)" 'infra/modules'
  }
  # 14. CA-NO-REVISION-SUFFIX — a hardcoded revisionSuffix fails Phase 2 redeploy ('revision already exists').
  if ($hasCA -and ($iac -match 'revisionSuffix\s*:')) {
    Add-Fail 'CA-NO-REVISION-SUFFIX' 'Container App sets revisionSuffix — omit it (ARM auto-generates); a hardcoded value fails Phase 2 redeploy' 'infra/modules'
  }
  # 15. CA-IMAGE-PARAM — two-phase deploy needs `param containerImage` in main.bicep, else the Phase 2 `--parameters containerImage=` override is silently ignored and the placeholder image persists.
  if ($hasCA -and $hasAcr -and ($mainBicep -notmatch 'param\s+containerImage')) {
    Add-Fail 'CA-IMAGE-PARAM' 'main.bicep lacks `param containerImage` — the Phase 2 image override is silently ignored and the placeholder persists (MANIFEST_UNKNOWN)' 'infra/main.bicep'
  }
  # 16. ACRPULL-GUID — near-miss detector: the fixed AcrPull prefix present without the canonical full GUID = wrong last segment (hallucinated) → RoleDefinitionDoesNotExist. Cannot false-positive.
  if (($iac -match '7f951dda-4ed3-4680-a7ca-') -and ($iac -notmatch '7f951dda-4ed3-4680-a7ca-43fe172d538d')) {
    Add-Fail 'ACRPULL-GUID' 'AcrPull role GUID is wrong — canonical value is 7f951dda-4ed3-4680-a7ca-43fe172d538d (RoleDefinitionDoesNotExist otherwise)' 'infra/modules/role-assignments.bicep'
  }
  # 17. ACR-NO-PREMIUM-POLICY — retention/trust/quarantine are Premium-only; on Basic/Standard ACR they fail SkuNotSupported. FP-safe: skipped if any 'Premium' SKU appears in the IaC.
  if ($hasAcr -and ($iac -match '(retentionPolicy|trustPolicy|quarantinePolicy)\s*:') -and ($iac -notmatch "'Premium'")) {
    Add-Fail 'ACR-NO-PREMIUM-POLICY' 'ACR has a Premium-only policy (retention/trust/quarantine) but is not Premium — omit these for Basic/Standard (SkuNotSupported at deploy)' 'infra/modules'
  }
}

# 9. WARN-FIXED — prereq warnings flagged fixPhase:"scaffold" must land in the generated IaC.
#    Only warnings with a provable signal are enforced; unverifiable ones are skipped (no false BLOCK).
#    Extend $warnSignal as new provable scaffold-phase warning IDs are added.
$prereq = Read-Json (Join-Path $SessionPath 'prereq-output.json')
if ($prereq -and $prereq.warnings) {
  $warnSignal = @{
    'W-PG-SSL'   = @{ kind = 'iac';  pattern = 'PGSSLMODE|sslmode' }   # SSL-mode env var emitted in IaC
    'W-BUILDKIT' = @{ kind = 'file'; pattern = 'Dockerfile.azure' }     # ACR-compatible Dockerfile emitted
  }
  foreach ($w in $prereq.warnings) {
    if ($w.fixPhase -ne 'scaffold') { continue }
    $sig = $warnSignal[$w.id]
    if (-not $sig) { continue }   # no deterministic signal — cannot verify, do not block
    $present = if ($sig.kind -eq 'file') {
      [bool](Get-ChildItem -Recurse -Filter $sig.pattern -ErrorAction SilentlyContinue | Select-Object -First 1)
    } else {
      [bool]($iac -match $sig.pattern)
    }
    if (-not $present) {
      Add-Fail 'WARN-FIXED' "prereq warning '$($w.id)' (fixPhase:scaffold) fix not found in IaC — $($w.fix)" 'infra/'
    }
  }
}

$result = [ordered]@{ passed = ($failures.Count -eq 0); failures = $failures }
$result | ConvertTo-Json -Depth 5 -Compress
if ($failures.Count -gt 0) { exit 1 } else { exit 0 }
