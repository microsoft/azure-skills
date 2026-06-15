#!/usr/bin/env bash
# verify-environment.sh
# Verifies the local environment for creating a hosted Foundry agent with `azd ai`.
# Runs all the read-only checks in one pass and prints a single concise summary,
# so the agent does not have to run (and reason over) each azd command separately.
#
# Usage:
#   ./verify-environment.sh
#
# Output: human-readable summary lines, each prefixed with [OK], [WARN], or [ACTION].
# Exit code: 0 if no blocking actions, 1 if at least one [ACTION] is required.

set -uo pipefail

ACTION_REQUIRED=0

note_ok()     { echo "[OK] $1"; }
note_warn()   { echo "[WARN] $1"; }
note_action() { echo "[ACTION] $1"; ACTION_REQUIRED=1; }

# Refresh PATH to pick up recently-installed tools (e.g. azd installed in same session)
if [ -f /etc/environment ]; then
  # shellcheck disable=SC1091
  . /etc/environment 2>/dev/null || true
fi
hash -r 2>/dev/null || true

# 1. azd present + version
if ! command -v azd >/dev/null 2>&1; then
  note_action "Azure Developer CLI (azd) is not installed. Install it from https://aka.ms/azd-install, then re-run."
  echo ""
  echo "Summary: azd missing -- cannot continue."
  exit 1
fi

AZD_VERSION="$(azd version --output json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("azd",{}).get("version","unknown"))' 2>/dev/null || echo unknown)"
note_ok "azd installed (version ${AZD_VERSION})."

# 2. Required extensions
EXT_JSON="$(azd extension list --output json 2>/dev/null || echo '[]')"
for ext in azure.ai.agents azure.ai.projects; do
  if printf '%s' "$EXT_JSON" | grep -q "$ext"; then
    note_ok "Extension '$ext' is installed."
  else
    note_action "Extension '$ext' is missing. Run: azd extension install $ext"
  fi
done

# 3. Auth status
if azd auth login --check-status >/dev/null 2>&1; then
  note_ok "Logged in to azd."
else
  note_action "Not logged in. Ask the user to run 'azd auth login' (it opens a browser; never run it for them)."
fi

# 4. Foundry project endpoint (optional at this stage)
# Short-circuit when there's no azd project in cwd: `azd ai project show` / `agent show`
# would just return nothing after a ~3s subprocess each.
if [ ! -f "azure.yaml" ]; then
  note_warn "No Foundry project endpoint set yet. A new project will be created at provision/deploy time, or supply an existing project resource ID."
  note_ok "No agent deployed yet. Proceed with create."
else
  PROJECT_JSON="$(azd ai project show --output json 2>/dev/null || echo '')"
  ENDPOINT=""
  if [ -n "$PROJECT_JSON" ]; then
    ENDPOINT="$(printf '%s' "$PROJECT_JSON" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    print(""); raise SystemExit
if isinstance(d,dict):
    for k in ("endpoint","projectEndpoint","aiProjectEndpoint"):
        if d.get(k):
            print(d[k]); break
' 2>/dev/null)"
  fi
  if [ -n "$ENDPOINT" ]; then
    note_ok "Foundry project endpoint configured: ${ENDPOINT}"
  else
    note_warn "No Foundry project endpoint set yet. A new project will be created at provision/deploy time, or supply an existing project resource ID."
  fi

  # 5. Agent deployment status
  AGENT_JSON="$(azd ai agent show --output json 2>/dev/null || echo '')"
  if [ -n "$AGENT_JSON" ]; then
    STATUS="$(printf '%s' "$AGENT_JSON" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    print("unknown"); raise SystemExit
print(d.get("status","unknown") if isinstance(d,dict) else "unknown")' 2>/dev/null)"
    case "$STATUS" in
      active|deployed) note_ok "An agent is already deployed (status: ${STATUS}). Skip to deploy.md to redeploy, or tools to add a tool." ;;
      not_deployed)    note_ok "No agent deployed yet (status: not_deployed). Proceed with create." ;;
      *)               note_warn "Agent status: ${STATUS}." ;;
    esac
  else
    note_ok "No agent deployed yet. Proceed with create."
  fi
fi

echo ""
if [ "$ACTION_REQUIRED" -eq 1 ]; then
  echo "Summary: action required -- resolve the [ACTION] items above before continuing."
  exit 1
else
  echo "Summary: environment ready for 'azd ai' hosted-agent creation."
  exit 0
fi
