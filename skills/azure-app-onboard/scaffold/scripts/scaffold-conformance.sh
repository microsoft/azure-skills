#!/usr/bin/env bash
# Scaffold -> Deploy conformance gate (bash twin of scaffold-conformance.ps1).
# Checks generated IaC against the plan for semantic defects `az bicep build` cannot catch.
#
# Usage:  scaffold-conformance.sh <sessionPath> [infraPath]
# Output: JSON { passed, failures:[{id,detail,file}] } to stdout.
# Exit:   0 = pass, 1 = one or more BLOCK failures.
#
# Pure-text checks (tags, TLS, purge, deployer role, plaintext secret) always run.
# Plan-dependent checks (version, services-complete, db-name, warn-fixed) run only when `jq` is present.
set -u
SESSION_PATH="${1:?usage: scaffold-conformance.sh <sessionPath> [infraPath]}"
INFRA_PATH="${2:-infra}"

PLAN="$SESSION_PATH/prepare-plan.json"
MAIN="$INFRA_PATH/main.bicep"
PARAMS="$INFRA_PATH/main.parameters.json"

main_bicep="$( [ -f "$MAIN" ] && cat "$MAIN" || true )"
params_raw="$( [ -f "$PARAMS" ] && cat "$PARAMS" || true )"
iac="$( find "$INFRA_PATH" -name '*.bicep' -type f 2>/dev/null -exec cat {} + || true )"

HAVE_JQ=0; command -v jq >/dev/null 2>&1 && HAVE_JQ=1

# failures accumulator (JSON objects, newline-separated)
fails=""
add_fail() { # id detail file
  local obj; obj="$(printf '{"id":"%s","detail":"%s","file":"%s"}' "$1" "$2" "$3")"
  fails="${fails:+$fails,}$obj"
}
iac_has() { printf '%s' "$iac" | grep -qE "$1"; }

# 1. TAGS-NO-CAMEL
if printf '%s' "$main_bicep" | grep -qE 'appOnboard(Skill|SessionId)|createdAt:|deployedBy:'; then
  add_fail "TAGS-NO-CAMEL" "camelCase tag keys found — use hyphenated ('app-onboard-skill' ...)" "infra/main.bicep"
fi

# 12. DIAG-GATED — we don't scaffold diagnostic-settings; if present it must be gated behind enableDiagnostics (default false) or removed. Unconditional wiring blocks the first deploy.
#     Match an actual diagnostic module/resource declaration, not a prose comment mentioning 'diagnostic'.
if printf '%s' "$main_bicep" | grep -qE 'module[[:space:]]+[A-Za-z]*[Dd]iagnostic|Microsoft\.Insights/diagnosticSettings' && ! printf '%s' "$main_bicep" | grep -q 'enableDiagnostics'; then
  add_fail "DIAG-GATED" "diagnostic-settings module wired without an enableDiagnostics gate — gate it (module ... = if (enableDiagnostics), default false) or remove it; unconditional wiring blocks the first deploy" "infra/main.bicep"
fi

# 2. NO-PLAINTEXT-SECRET (jq-free: awk over the params file so it runs on hosts without jq)
if [ -n "$params_raw" ]; then
  bad_keys="$(printf '%s' "$params_raw" | awk '
    { line=tolower($0) }
    line ~ /"[a-z0-9_]*(password|secret|connstring|connection)[a-z0-9_]*"[ \t]*:/ {
      n=split($0, parts, "\"")
      for (i=1;i<=n;i++) { if (tolower(parts[i]) ~ /(password|secret|connstring|connection)/) { pend=parts[i]; break } }
    }
    pend != "" && line ~ /"value"[ \t]*:[ \t]*"[^"]+"/ { print pend; pend="" }
    /}/ { pend="" }
  ')"
  if [ -n "$bad_keys" ]; then
    while IFS= read -r k; do
      [ -z "$k" ] && continue
      add_fail "NO-PLAINTEXT-SECRET" "parameter '$k' has a literal value — must be @secure(), passed at deploy" "infra/main.parameters.json"
    done <<< "$bad_keys"
  fi
fi

# 2b. NO-BICEP-LITERAL-SECRET (pure-text) — secret values must be @secure() params, never quoted literals.
#     Property name must end in 'password'/'connectionString' right before ':' (so 'secretName' etc. never match).
if [ -n "$iac" ]; then
  if printf '%s' "$iac" | grep -qiE "[A-Za-z]*(password|connectionstring)[[:space:]]*:[[:space:]]*'[^']+'"; then
    k="$(printf '%s' "$iac" | grep -oiE "[A-Za-z]*(password|connectionstring)[[:space:]]*:[[:space:]]*'[^']+'" | head -n1 | sed -E "s/[[:space:]]*:.*//")"
    add_fail "NO-BICEP-LITERAL-SECRET" "property '$k' assigned a literal secret in Bicep — use an @secure() param passed at deploy" "infra/"
  fi
  if printf '%s' "$iac" | grep -qE ":[[:space:]]*'[^']*(Password=|AccountKey=|SharedAccessKey=|://[^:@/ ]+:[^:@/ ]+@)[^']*'"; then
    add_fail "NO-BICEP-LITERAL-SECRET" "quoted literal contains an embedded credential (Password=/AccountKey=/user:pass@) in Bicep — use an @secure() param" "infra/"
  fi
fi

# service-name -> resource-type map (longest keys first so 'container apps environment' wins)
declare -a MAP_KEYS=( "container apps environment" "container app" "container registry" "mysql" "postgres" \
  "key vault" "log analytics" "application insights" "static web app" "app service" "functions" \
  "sql" "cosmos" "redis" "storage" "service bus" "event hub" )
map_type() {
  case "$1" in
    *"container apps environment"*) echo 'Microsoft\.App/managedEnvironments';;
    *"container app"*)              echo 'Microsoft\.App/containerApps';;
    *"container registry"*)         echo 'Microsoft\.ContainerRegistry/registries';;
    *mysql*)                        echo 'Microsoft\.DBforMySQL/flexibleServers';;
    *postgres*)                     echo 'Microsoft\.DBforPostgreSQL/flexibleServers';;
    *"key vault"*)                  echo 'Microsoft\.KeyVault/vaults';;
    *"log analytics"*)              echo 'Microsoft\.OperationalInsights/workspaces';;
    *"application insights"*)       echo 'Microsoft\.Insights/components';;
    *"static web app"*)             echo 'Microsoft\.Web/staticSites';;
    *"app service"*|*functions*)    echo 'Microsoft\.Web/sites';;
    *sql*)                          echo 'Microsoft\.Sql/servers';;
    *cosmos*)                       echo 'Microsoft\.DocumentDB/databaseAccounts';;
    *redis*)                        echo 'Microsoft\.Cache/redis';;
    *storage*)                      echo 'Microsoft\.Storage/storageAccounts';;
    *"service bus"*)                echo 'Microsoft\.ServiceBus/namespaces';;
    *"event hub"*)                  echo 'Microsoft\.EventHub/namespaces';;
    *) echo '';;
  esac
}

svc_names=""; db_version=""; app_db_name=""; has_mysql=0; has_pg=0
if [ "$HAVE_JQ" = 1 ] && [ -f "$PLAN" ]; then
  svc_names="$(jq -r '.services[].name' "$PLAN" 2>/dev/null)"
  app_db_name="$(jq -r '.appDbName // empty' "$PLAN" 2>/dev/null)"
  printf '%s' "$svc_names" | grep -qiE 'mysql'      && has_mysql=1
  printf '%s' "$svc_names" | grep -qiE 'postgres'   && has_pg=1

  # 3. SERVICES-COMPLETE
  while IFS= read -r name; do
    [ -z "$name" ] && continue
    lc="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')"
    expected="$(map_type "$lc")"
    if [ -n "$expected" ] && ! iac_has "$expected"; then
      add_fail "SERVICES-COMPLETE" "planned service '$name' has no matching resource ($expected) in IaC" "infra/"
    fi
  done < <(printf '%s\n' "$svc_names")
else
  # jq absent: fall back to grep for the DB-type presence (drives TLS/name checks below)
  printf '%s' "$iac" | grep -qE 'Microsoft\.DBforMySQL/flexibleServers'      && has_mysql=1
  printf '%s' "$iac" | grep -qE 'Microsoft\.DBforPostgreSQL/flexibleServers' && has_pg=1
fi

# --- Managed database checks ---
if [ "$has_mysql" = 1 ] || [ "$has_pg" = 1 ]; then
  # 4. DB-VERSION-MATCH — each server's version must equal its capabilities-verified plan value.
  #    Scope the match to the DB resource block so an unrelated 'version:' elsewhere isn't picked up.
  if [ "$HAVE_JQ" = 1 ] && [ -f "$PLAN" ]; then
    while IFS=$'\t' read -r dbkind dbver; do
      [ -z "$dbver" ] && continue
      case "$dbkind" in
        *MySQL*) marker='Microsoft[.]DBforMySQL/flexibleServers';;
        *)       marker='Microsoft[.]DBforPostgreSQL/flexibleServers';;
      esac
      iac_ver="$(printf '%s\n' "$iac" | awk -v marker="$marker" '
        $0 ~ marker { armed=1 }
        armed==1 && match($0, /version:[ \t]*'"'"'[^'"'"']+'"'"'/) {
          v=substr($0,RSTART,RLENGTH); sub(/version:[ \t]*'"'"'/,"",v); sub(/'"'"'.*/,"",v); print v; exit
        }')"
      if [ -n "$iac_ver" ] && [ "$iac_ver" != "$dbver" ]; then
        add_fail "DB-VERSION-MATCH" "$dbkind IaC version '$iac_ver' != plan '$dbver'" "infra/modules"
      fi
    done < <(jq -r '.services[]? | select(.name|test("MySQL|PostgreSQL")) | [.name, (.version // "")] | @tsv' "$PLAN" 2>/dev/null)
  fi
  # 5. DB-TLS-ON (MySQL, pure-text)
  if [ "$has_mysql" = 1 ] && ! iac_has 'require_secure_transport'; then
    add_fail "DB-TLS-ON" "MySQL module missing require_secure_transport config" "infra/modules"
  fi
  # 6. DB-NAME-PRESENT (needs plan.appDbName from jq)
  if [ -n "$app_db_name" ] && ! iac_has 'flexibleServers/databases'; then
    add_fail "DB-NAME-PRESENT" "app DB '$app_db_name' declared but no flexibleServers/databases resource" "infra/modules"
  fi
  # 10. MYSQL-NO-NETWORK-BLOCK (MySQL, pure-text) — public flow must omit the network block;
  #     an empty delegatedSubnetResourceId is rejected by ARM (LinkedInvalidPropertyId).
  if [ "$has_mysql" = 1 ] && iac_has 'delegatedSubnetResourceId|privateDnsZoneResourceId'; then
    add_fail "MYSQL-NO-NETWORK-BLOCK" "MySQL module includes a network block (delegatedSubnetResourceId) — omit it for public access; an empty value is rejected by ARM" "infra/modules"
  fi
  # 11. DB-LOGIN-NOT-RESERVED (pure-text) — administratorLogin must not be an Azure-reserved name.
  if iac_has "administratorLogin:[[:space:]]*'(root|admin|administrator|guest|public|sa|azure_superuser|azure_pg_admin)'"; then
    resv="$(printf '%s' "$iac" | grep -oE "administratorLogin:[[:space:]]*'[^']+'" | grep -oiE "(root|admin|administrator|guest|public|sa|azure_superuser|azure_pg_admin)" | head -n1)"
    add_fail "DB-LOGIN-NOT-RESERVED" "administratorLogin uses a reserved name ('${resv}') — derive a safe login (e.g. '{project}admin'), never a compose-sourced reserved name" "infra/modules"
  fi
fi

# --- Key Vault checks (pure-text) ---
if iac_has 'Microsoft\.KeyVault/vaults'; then
  # 7. KV-NO-PURGE
  if iac_has 'enablePurgeProtection'; then
    add_fail "KV-NO-PURGE" "enablePurgeProtection present — omit it (policy may reject false)" "infra/modules"
  fi
  # 8. KV-DEPLOYER-ROLE
  has_officer=0; iac_has 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7' && has_officer=1
  has_param=0; { iac_has 'deployerObjectId' || printf '%s' "$params_raw" | grep -q 'deployerObjectId'; } && has_param=1
  if [ "$has_officer" != 1 ] || [ "$has_param" != 1 ]; then
    add_fail "KV-DEPLOYER-ROLE" "missing deployer Key Vault Secrets Officer role and/or deployerObjectId param" "infra/modules/role-assignments.bicep"
  fi
fi

# --- Container Apps / ACR checks (deterministic ARM-failure invariants) ---
if [ -n "$iac" ]; then
  has_ca=0;  iac_has 'Microsoft\.App/containerApps'            && has_ca=1
  has_cae=0; iac_has 'Microsoft\.App/managedEnvironments'      && has_cae=1
  has_acr=0; iac_has 'Microsoft\.ContainerRegistry/registries' && has_acr=1
  # 13. CAE-APPLOGS — managedEnvironments log config MUST nest under appLogsConfiguration; a bare
  #     top-level logAnalyticsConfiguration fails deploy with ManagedEnvironmentInvalidSchema.
  if [ "$has_cae" = 1 ] && iac_has 'logAnalyticsConfiguration' && ! iac_has 'appLogsConfiguration'; then
    add_fail "CAE-APPLOGS" "Container Apps Environment uses a bare logAnalyticsConfiguration — nest it under appLogsConfiguration.destination='log-analytics' (else ManagedEnvironmentInvalidSchema at deploy)" "infra/modules"
  fi
  # 14. CA-NO-REVISION-SUFFIX — a hardcoded revisionSuffix fails Phase 2 redeploy ('revision already exists').
  if [ "$has_ca" = 1 ] && iac_has 'revisionSuffix[[:space:]]*:'; then
    add_fail "CA-NO-REVISION-SUFFIX" "Container App sets revisionSuffix — omit it (ARM auto-generates); a hardcoded value fails Phase 2 redeploy" "infra/modules"
  fi
  # 15. CA-IMAGE-PARAM — two-phase deploy needs 'param containerImage' in main.bicep, else the Phase 2 override is silently ignored and the placeholder image persists.
  if [ "$has_ca" = 1 ] && [ "$has_acr" = 1 ] && ! printf '%s' "$main_bicep" | grep -qE 'param[[:space:]]+containerImage'; then
    add_fail "CA-IMAGE-PARAM" "main.bicep lacks 'param containerImage' — the Phase 2 image override is silently ignored and the placeholder persists (MANIFEST_UNKNOWN)" "infra/main.bicep"
  fi
  # 16. ACRPULL-GUID — near-miss detector: fixed AcrPull prefix present without the canonical full GUID = hallucinated last segment → RoleDefinitionDoesNotExist. Cannot false-positive.
  if iac_has '7f951dda-4ed3-4680-a7ca-' && ! iac_has '7f951dda-4ed3-4680-a7ca-43fe172d538d'; then
    add_fail "ACRPULL-GUID" "AcrPull role GUID is wrong — canonical value is 7f951dda-4ed3-4680-a7ca-43fe172d538d (RoleDefinitionDoesNotExist otherwise)" "infra/modules/role-assignments.bicep"
  fi
  # 17. ACR-NO-PREMIUM-POLICY — retention/trust/quarantine are Premium-only; on Basic/Standard ACR they fail SkuNotSupported. FP-safe: skipped if any 'Premium' SKU appears.
  if [ "$has_acr" = 1 ] && iac_has '(retentionPolicy|trustPolicy|quarantinePolicy)[[:space:]]*:' && ! iac_has "'Premium'"; then
    add_fail "ACR-NO-PREMIUM-POLICY" "ACR has a Premium-only policy (retention/trust/quarantine) but is not Premium — omit these for Basic/Standard (SkuNotSupported at deploy)" "infra/modules"
  fi
fi

# 9. WARN-FIXED (needs jq to read prereq-output.json warnings[]) — prereq warnings flagged
#    fixPhase:"scaffold" must land in the IaC. Only warnings with a provable signal are enforced;
#    unverifiable ones are skipped (no false BLOCK). Extend the case map for new provable warning IDs.
PREREQ="$SESSION_PATH/prereq-output.json"
if [ "$HAVE_JQ" = 1 ] && [ -f "$PREREQ" ]; then
  while IFS=$'\t' read -r wid wfix; do
    [ -z "$wid" ] && continue
    present=0
    case "$wid" in
      W-PG-SSL)   printf '%s' "$iac" | grep -qiE 'PGSSLMODE|sslmode' && present=1 ;;
      W-BUILDKIT) [ -n "$(find . -name 'Dockerfile.azure' -type f 2>/dev/null | head -n1)" ] && present=1 ;;
      *) continue ;;   # no deterministic signal — cannot verify, do not block
    esac
    if [ "$present" != 1 ]; then
      add_fail "WARN-FIXED" "prereq warning '$wid' (fixPhase:scaffold) fix not found in IaC — $wfix" "infra/"
    fi
  done < <(jq -r '.warnings[]? | select(.fixPhase=="scaffold") | [.id, .fix] | @tsv' "$PREREQ" 2>/dev/null)
fi

if [ -z "$fails" ]; then
  printf '{"passed":true,"failures":[]}\n'
  exit 0
else
  printf '{"passed":false,"failures":[%s]}\n' "$fails"
  exit 1
fi
