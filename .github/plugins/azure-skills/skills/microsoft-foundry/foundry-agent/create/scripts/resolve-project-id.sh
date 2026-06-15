#!/usr/bin/env bash
# resolve-project-id.sh
# Resolves a Foundry project ARM resource ID from a Foundry project endpoint.
# The endpoint is used only for Azure lookup keys; the printed ID is the `id`
# returned by Azure CLI, not a locally constructed ARM resource ID.
#
# Usage:
#   ./resolve-project-id.sh --endpoint "https://my-account.services.ai.azure.com/api/projects/my-project"
#   ./resolve-project-id.sh --endpoint "https://my-account.services.ai.azure.com/api/projects/my-project" --output json

set -uo pipefail

ENDPOINT=""
SUBSCRIPTION=""
RESOURCE_GROUP=""
ACCOUNT_NAME=""
PROJECT_NAME=""
OUTPUT="id"
TEMP_FILES=()

cleanup() {
  if [ "${#TEMP_FILES[@]}" -gt 0 ]; then
    rm -f "${TEMP_FILES[@]}"
  fi
}
trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage: resolve-project-id.sh --endpoint <foundry-project-endpoint> [options]

Options:
  -e, --endpoint <url>          Foundry project endpoint. Required.
      --subscription <id>       Azure subscription ID or name.
  -g, --resource-group <name>   Resource group for the Foundry account.
  -n, --account-name <name>     Foundry account name.
      --project-name <name>     Foundry project name.
  -o, --output <id|json>        Output format. Default: id.
  -h, --help                    Show this help.
EOF
}

fatal() {
  echo "[ERROR] $1" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    -e|--endpoint)
      [ "$#" -ge 2 ] || fatal "$1 requires a value."
      ENDPOINT="$2"
      shift 2
      ;;
    --subscription)
      [ "$#" -ge 2 ] || fatal "$1 requires a value."
      SUBSCRIPTION="$2"
      shift 2
      ;;
    -g|--resource-group)
      [ "$#" -ge 2 ] || fatal "$1 requires a value."
      RESOURCE_GROUP="$2"
      shift 2
      ;;
    -n|--account-name)
      [ "$#" -ge 2 ] || fatal "$1 requires a value."
      ACCOUNT_NAME="$2"
      shift 2
      ;;
    --project-name)
      [ "$#" -ge 2 ] || fatal "$1 requires a value."
      PROJECT_NAME="$2"
      shift 2
      ;;
    -o|--output)
      [ "$#" -ge 2 ] || fatal "$1 requires a value."
      OUTPUT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fatal "Unknown argument: $1"
      ;;
  esac
done

[ -n "$ENDPOINT" ] || fatal "--endpoint is required."
[ "$OUTPUT" = "id" ] || [ "$OUTPUT" = "json" ] || fatal "--output must be 'id' or 'json'."

command -v az >/dev/null 2>&1 || fatal "Azure CLI 'az' was not found on PATH."
command -v python3 >/dev/null 2>&1 || fatal "python3 was not found on PATH."

PARSED_ENDPOINT="$(
  python3 - "$ENDPOINT" "$ACCOUNT_NAME" "$PROJECT_NAME" <<'PY'
import json
import sys
from urllib.parse import unquote, urlparse

endpoint = (sys.argv[1] or "").strip().rstrip("/")
account_name = sys.argv[2] or ""
project_name = sys.argv[3] or ""

parsed = urlparse(endpoint)
if parsed.scheme not in ("http", "https") or not parsed.netloc:
    print("Endpoint must be an http or https URI.", file=sys.stderr)
    raise SystemExit(1)

if not project_name:
    parts = [unquote(p) for p in parsed.path.strip("/").split("/") if p]
    for index, part in enumerate(parts):
        if part.lower() == "projects" and index + 1 < len(parts):
            project_name = parts[index + 1]
            break

if not account_name:
    host = parsed.hostname or ""
    suffix = ".services.ai.azure.com"
    if host.lower().endswith(suffix):
        account_name = host[:-len(suffix)]

print(json.dumps({
    "endpoint": endpoint,
    "accountName": account_name,
    "projectName": project_name,
}))
PY
)" || fatal "Could not parse Foundry project endpoint."

NORMALIZED_ENDPOINT="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["endpoint"])' <<<"$PARSED_ENDPOINT")"
if [ -z "$ACCOUNT_NAME" ]; then
  ACCOUNT_NAME="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["accountName"])' <<<"$PARSED_ENDPOINT")"
fi
if [ -z "$PROJECT_NAME" ]; then
  PROJECT_NAME="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["projectName"])' <<<"$PARSED_ENDPOINT")"
fi

[ -n "$ACCOUNT_NAME" ] || fatal "Could not read the account name from the endpoint host. Re-run with --account-name."
[ -n "$PROJECT_NAME" ] || fatal "Could not read the project name from the endpoint path. Re-run with --project-name."

add_subscription_arg() {
  if [ -n "$SUBSCRIPTION" ]; then
    printf '%s\n' "--subscription" "$SUBSCRIPTION"
  fi
}

run_az_json() {
  local stderr_file
  stderr_file="$(mktemp)"
  local output
  if output="$(az "$@" 2>"$stderr_file")"; then
    rm -f "$stderr_file"
    printf '%s' "$output"
    return 0
  fi
  local error_text
  error_text="$(cat "$stderr_file")"
  rm -f "$stderr_file"
  echo "$error_text" >&2
  return 1
}

if [ -z "$RESOURCE_GROUP" ]; then
  AZ_ARGS=(cognitiveservices account list -o json)
  while IFS= read -r arg; do
    [ -n "$arg" ] && AZ_ARGS+=("$arg")
  done < <(add_subscription_arg)

  ACCOUNTS_JSON="$(run_az_json "${AZ_ARGS[@]}")" || fatal "Failed to list Cognitive Services accounts."
  ACCOUNTS_FILE="$(mktemp)"
  TEMP_FILES+=("$ACCOUNTS_FILE")
  printf '%s' "$ACCOUNTS_JSON" >"$ACCOUNTS_FILE"
  MATCHED_ACCOUNT="$(
    ACCOUNT_NAME="$ACCOUNT_NAME" python3 - "$ACCOUNTS_FILE" <<'PY'
import json
import os
import sys

target = os.environ["ACCOUNT_NAME"].lower()
with open(sys.argv[1], encoding="utf-8") as handle:
    accounts = json.load(handle)
matches = []
for account in accounts:
    name = (account.get("name") or "")
    custom = ((account.get("properties") or {}).get("customSubDomainName") or "")
    if name.lower() == target or custom.lower() == target:
        matches.append(account)

if not matches:
    print(f"Could not find a Cognitive Services account matching '{os.environ['ACCOUNT_NAME']}'.", file=sys.stderr)
    raise SystemExit(1)
if len(matches) > 1:
    choices = ", ".join(f"{m.get('resourceGroup')}/{m.get('name')}" for m in matches)
    print(f"Multiple accounts matched '{os.environ['ACCOUNT_NAME']}': {choices}. Re-run with --resource-group.", file=sys.stderr)
    raise SystemExit(1)

print(json.dumps({
    "resourceGroup": matches[0].get("resourceGroup") or "",
    "accountName": matches[0].get("name") or "",
}))
PY
  )" || fatal "Failed to resolve the Foundry account resource group."

  RESOURCE_GROUP="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["resourceGroup"])' <<<"$MATCHED_ACCOUNT")"
  ACCOUNT_NAME="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["accountName"])' <<<"$MATCHED_ACCOUNT")"
fi

PROJECT_JSON=""
AZ_SHOW_ARGS=(
  cognitiveservices account project show
  -g "$RESOURCE_GROUP"
  -n "$ACCOUNT_NAME"
  --project-name "$PROJECT_NAME"
  -o json
)
while IFS= read -r arg; do
  [ -n "$arg" ] && AZ_SHOW_ARGS+=("$arg")
done < <(add_subscription_arg)

if ! PROJECT_JSON="$(run_az_json "${AZ_SHOW_ARGS[@]}")"; then
  AZ_LIST_ARGS=(
    cognitiveservices account project list
    -g "$RESOURCE_GROUP"
    -n "$ACCOUNT_NAME"
    -o json
  )
  while IFS= read -r arg; do
    [ -n "$arg" ] && AZ_LIST_ARGS+=("$arg")
  done < <(add_subscription_arg)

  PROJECTS_JSON="$(run_az_json "${AZ_LIST_ARGS[@]}")" || fatal "Failed to list Foundry projects."
  PROJECTS_FILE="$(mktemp)"
  TEMP_FILES+=("$PROJECTS_FILE")
  printf '%s' "$PROJECTS_JSON" >"$PROJECTS_FILE"
  PROJECT_JSON="$(
    NORMALIZED_ENDPOINT="$NORMALIZED_ENDPOINT" python3 - "$PROJECTS_FILE" <<'PY'
import json
import os
import sys

expected = os.environ["NORMALIZED_ENDPOINT"].rstrip("/")
with open(sys.argv[1], encoding="utf-8") as handle:
    projects = json.load(handle)

def endpoints(project):
    values = ((project.get("properties") or {}).get("endpoints") or {}).values()
    return [value.rstrip("/") for value in values if isinstance(value, str) and value]

for project in projects:
    if expected in endpoints(project):
        print(json.dumps(project))
        break
else:
    print(f"Could not find a Foundry project matching endpoint '{expected}'.", file=sys.stderr)
    raise SystemExit(1)
PY
  )" || fatal "Failed to resolve the Foundry project from endpoint metadata."
fi

PROJECT_JSON="$PROJECT_JSON" \
NORMALIZED_ENDPOINT="$NORMALIZED_ENDPOINT" \
RESOURCE_GROUP="$RESOURCE_GROUP" \
ACCOUNT_NAME="$ACCOUNT_NAME" \
PROJECT_NAME="$PROJECT_NAME" \
OUTPUT="$OUTPUT" \
python3 - <<'PY'
import json
import os

project = json.loads(os.environ["PROJECT_JSON"])
expected = os.environ["NORMALIZED_ENDPOINT"].rstrip("/")
endpoint_values = ((project.get("properties") or {}).get("endpoints") or {}).values()
endpoints = [value.rstrip("/") for value in endpoint_values if isinstance(value, str) and value]

if endpoints and expected not in endpoints:
    print(f"[ERROR] Resolved project endpoint metadata did not match '{expected}'.", file=__import__("sys").stderr)
    raise SystemExit(1)

resource_id = project.get("id")
if not resource_id:
    print("[ERROR] Azure returned a project object without an id.", file=__import__("sys").stderr)
    raise SystemExit(1)

if os.environ["OUTPUT"] == "json":
    print(json.dumps({
        "id": resource_id,
        "endpoint": endpoints[0] if endpoints else expected,
        "resourceGroup": os.environ["RESOURCE_GROUP"],
        "accountName": os.environ["ACCOUNT_NAME"],
        "projectName": os.environ["PROJECT_NAME"],
    }, indent=2))
else:
    print(resource_id)
PY
