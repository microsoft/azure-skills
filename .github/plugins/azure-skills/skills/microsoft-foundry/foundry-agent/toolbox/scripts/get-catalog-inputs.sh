#!/usr/bin/env bash
# Discover catalog inputs for Foundry catalog MCP connections and classify which
# auth types each matching connector supports: MANAGED OAUTH and/or USER ENTRA TOKEN.
#
# For each match it prints:
#   - toolEntityId   -> azd ai connection create --metadata toolEntityId=...
#   - serverUrl      -> azd ai connection create --target ...   (best-effort; see note)
#   - managedOAuth   -> true when Foundry can broker the connector's OAuth app
#   - connectorName  -> (managed only) the brokered app for --connector-name (e.g. foundrygithubmcp)
#   - userEntraToken -> true when the tile forwards the caller's Entra identity
#   - audience       -> (user-entra-token only) the value --audience needs
#   - scopes         -> OAuth scopes advertised by the tool
#
# Usage:  ./get-catalog-inputs.sh [connector-name-substring] [--managed-oauth|--user-entra-token]
#         The name substring is OPTIONAL — omit it to list every MCP tile.
# Example: ./get-catalog-inputs.sh                       # list ALL MCP tiles
#          ./get-catalog-inputs.sh --managed-oauth       # list all managed-OAuth tiles
#          ./get-catalog-inputs.sh --user-entra-token    # list all user-entra-token tiles
#          ./get-catalog-inputs.sh github                # narrow by name substring
#
# Requires: az (logged in), curl, python. The MCP catalog lives only in eastus,
# in the registry-prod-bl container (the public connectors-registry-prod-bl holds
# Logic Apps connectors, not MCP tools, so it is not queried).
#
# HOW AUTH TYPES ARE DETECTED (mirrors the portal, verified against
# app/src/components/tools/Config/ToolConfigFields.tsx + transformTools.tsx):
#   The asset-gallery search entity's `properties` carry the auth signals the portal
#   keys off — no separate managedApis call is needed:
#     * host = "remotes"       when kind == "mcp" and properties.remotes is non-empty.
#     * x-ms-connector-name    the Foundry-brokered OAuth app (e.g. "foundrygithubmcp").
#     * x-ms-auth-schemas      case-insensitive scheme keys (oauth2 / managedidentity /
#                              agentidentity); often EMPTY even for OAuth tiles.
#     * x-ms-security-schemes  the OpenAPI-style scheme block (declares oauth2, scopes).
#     * x-ms-audience          the resource the forwarded user token is scoped to.
#   MANAGED OAUTH (portal supportsManagedOAuth) = has x-ms-connector-name OR
#     x-ms-auth-schemas contains "oauth2". Foundry brokers the app; the config dialog
#     needs connector-name + toolEntityId and does NOT ask for an audience.
#     (github/vercel qualify via connector-name; sentinel/foundry-mcp via oauth2.)
#     work_iq / fabric_iq are hard-coded managed in the portal.
#   USER ENTRA TOKEN (Microsoft Entra -> Agent User Impersonation) = NO brokered
#     connector-name, but the tile declares an oauth2 scheme AND an x-ms-audience, so
#     the caller identity is forwarded. The config dialog REQUIRES that audience.
#     (work_iq, foundry-mcp, sentinel qualify.) A tile can support BOTH.
#
# NOTE on serverUrl: remotes[].url is often null in the index (verified for
# github). When empty, supply the connector's documented MCP endpoint as
# --target (e.g. github Copilot -> https://api.githubcopilot.com/mcp).
set -euo pipefail

NAME=""
FILTER="all"   # all | managed | entra
for arg in "$@"; do
  case "$arg" in
    --managed-oauth)     FILTER="managed" ;;
    --user-entra-token)  FILTER="entra" ;;
    -h|--help) echo "usage: get-catalog-inputs.sh [connector-name-substring] [--managed-oauth|--user-entra-token]" >&2; exit 0 ;;
    *) NAME="$arg" ;;
  esac
done
# NAME is OPTIONAL — with no substring the script lists every MCP tile in the registry.

GALLERY="https://eastus.api.azureml.ms/asset-gallery/v1.0/tools"
# Prefer real `python`; the bare `python3` on Windows is often a broken Store alias.
PY="$(command -v python || command -v python3 || true)"
[ -n "$PY" ] || { echo "error: python (or python3) is required" >&2; exit 2; }

TOKEN=$(az account get-access-token --resource "https://management.azure.com" --query accessToken -o tsv)

# Page through the MCP registry with NO name filter. This matters: adding an
# `annotations/name contains` filter makes the index return a THIN projection
# (only timestamps) that omits x-ms-auth-schemas / kind / remotes — the fields we
# classify on. Fetching unfiltered returns the full properties; we match $NAME
# client-side in the classifier. pageSize max is 100, so we page via continuationToken.
fetch_page() {
  local ct="$1" body
  if [ -n "$ct" ]; then
    body="{\"freeTextSearch\":\"*\",\"filters\":[{\"field\":\"entityContainerId\",\"operator\":\"eq\",\"values\":[\"registry-prod-bl\"]},{\"field\":\"type\",\"operator\":\"eq\",\"values\":[\"tools\"]}],\"pageSize\":100,\"continuationToken\":$ct}"
  else
    body="{\"freeTextSearch\":\"*\",\"filters\":[{\"field\":\"entityContainerId\",\"operator\":\"eq\",\"values\":[\"registry-prod-bl\"]},{\"field\":\"type\",\"operator\":\"eq\",\"values\":[\"tools\"]}],\"pageSize\":100}"
  fi
  curl -sS -X POST "$GALLERY" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$body"
}

echo "# Querying the MCP registry (registry-prod-bl) for '$NAME'..." >&2
# Collect all pages into one NDJSON-ish stream separated by \x1e for the classifier.
PAGES=""
CT=""
for _ in $(seq 1 10); do   # safety cap: 10 pages * 100 = 1000 entities
  PAGE=$(fetch_page "$CT")
  PAGES="${PAGES}${PAGE}"$'\x1e'
  CT=$(printf '%s' "$PAGE" | "$PY" -c 'import sys,json;d=json.load(sys.stdin);ct=d.get("continuationToken");print(json.dumps(ct) if ct else "")' 2>/dev/null)
  [ -n "$CT" ] || break
done

# Classify each entity from the index `properties` (the same fields the portal
# reads) and print a per-connector report, matched by $NAME and filtered by $FILTER.
printf '%s' "$PAGES" | FILTER="$FILTER" NAME="$NAME" "$PY" -c '
import sys, os, json, re

filt = os.environ.get("FILTER", "all")
HARDCODED_MANAGED = {"work_iq", "fabric_iq"}

def first_oauth_scope_key(props):
    # x-ms-security-schemes: { <name>: { type: "oauth2", flows: { authorizationCode: { scopes: {<aud>: <desc>} } } } }
    ss = props.get("x-ms-security-schemes") or {}
    if isinstance(ss, str):
        try: ss = json.loads(ss)
        except Exception: ss = {}
    for v in (ss.values() if isinstance(ss, dict) else []):
        if isinstance(v, dict) and v.get("type") == "oauth2":
            scopes = (((v.get("flows") or {}).get("authorizationCode") or {}).get("scopes")) or {}
            if isinstance(scopes, dict) and scopes:
                return next(iter(scopes.keys()))
    return ""

def all_scopes(props):
    ss = props.get("x-ms-security-schemes") or {}
    if isinstance(ss, str):
        try: ss = json.loads(ss)
        except Exception: ss = {}
    out = []
    for v in (ss.values() if isinstance(ss, dict) else []):
        if isinstance(v, dict) and v.get("type") == "oauth2":
            scopes = (((v.get("flows") or {}).get("authorizationCode") or {}).get("scopes")) or {}
            if isinstance(scopes, dict):
                out.extend(scopes.keys())
    return ",".join(out)

def has_oauth2_scheme(props):
    # True if x-ms-security-schemes declares an oauth2 scheme (the tile can do OAuth).
    ss = props.get("x-ms-security-schemes") or {}
    if isinstance(ss, str):
        try: ss = json.loads(ss)
        except Exception: ss = {}
    return any(isinstance(v, dict) and v.get("type") == "oauth2"
               for v in (ss.values() if isinstance(ss, dict) else []))

seen = {}
for blob in sys.stdin.read().split("\x1e"):
    blob = blob.strip()
    if not blob:
        continue
    try:
        doc = json.loads(blob)
    except json.JSONDecodeError:
        continue
    for r in doc.get("value", []) or []:
        eid = r.get("entityId", "")
        props = r.get("properties", {}) or {}
        m = re.search(r"objectId/([^/]+)", eid)
        conn = m.group(1) if m else ""
        tool_id = props.get("customProperties", {}).get("id") or r.get("name") or conn
        title = props.get("title") or ""
        name = (r.get("annotations", {}) or {}).get("name") or title or r.get("name") or conn

        # Client-side name match (the request carries no name filter — see script header).
        needle = os.environ.get("NAME", "").lower()
        if needle and needle not in f"{name} {conn} {title} {tool_id}".lower():
            continue

        remotes = props.get("remotes") or []
        url = (remotes[0].get("url") if remotes and isinstance(remotes[0], dict) else "") or ""
        host = "remotes" if (props.get("kind") == "mcp" and remotes) else (props.get("customProperties", {}).get("type") or "")

        schemes = props.get("x-ms-auth-schemas") or []
        if isinstance(schemes, str):
            try: schemes = json.loads(schemes)
            except Exception: schemes = [schemes]
        low = [str(s).lower() for s in schemes] if isinstance(schemes, list) else []

        connector_name = props.get("x-ms-connector-name") or ""   # Foundry-brokered app, e.g. "foundrygithubmcp"
        audience = props.get("x-ms-audience") or ""
        oauth2_scheme = has_oauth2_scheme(props)

        # Auth classification (mutually exclusive — one type per tile):
        #   user-entra-token = "oauth2" listed in x-ms-auth-schemas (foundry-mcp, M365
        #     frontier, dataverse, sentinel, fabric) — the portal commits UserEntraToken.
        #   managed OAuth = has an x-ms-connector-name (github/vercel) OR an oauth2
        #     security-scheme with NO managedidentity/agentidentity declared in
        #     x-ms-auth-schemas (work_iq, yutori, oracle...). work_iq / fabric_iq hard-coded.
        #   AGENT IDENTITY (excluded here) = x-ms-auth-schemas lists managedidentity or
        #     agentidentity (Azure Language, Azure Managed Grafana, Azure AI Search) —
        #     see tool-mcp-agent-identity.md. Key-auth / no-auth tiles are also excluded.
        is_remote = (host == "remotes")
        has_mi_agent = ("managedidentity" in low) or ("agentidentity" in low)
        entra   = is_remote and ("oauth2" in low)
        managed = (is_remote and (bool(connector_name) or (oauth2_scheme and not has_mi_agent)) or (str(tool_id).lower() in HARDCODED_MANAGED)) and not entra

        if not audience:
            audience = first_oauth_scope_key(props)
        scopes = all_scopes(props)

        # Dedup on objectId across versions/pages; prefer the record that actually
        # classified (managed/entra) or carries auth signals — a thin projection has none.
        key = conn or eid
        new_rich = managed or entra or bool(low) or bool(connector_name) or bool(audience)
        prev = seen.get(key)
        if prev is not None:
            old_rich = prev["managed"] or prev["entra"] or bool(prev["schemes"]) or bool(prev["connector_name"]) or bool(prev["audience"])
            if old_rich and not new_rich:
                continue
        seen[key] = dict(name=name, title=title, conn=conn, eid=eid, url=url, host=host,
                         schemes=",".join(low), connector_name=connector_name,
                         managed=managed, entra=entra,
                         audience=audience, scopes=scopes)

count = 0
for r in seen.values():
    if not r["conn"]:
        continue
    if filt == "managed" and not r["managed"]:
        continue
    if filt == "entra" and not r["entra"]:
        continue
    count += 1
    print()
    print("  name           : " + str(r["name"]))
    print("  displayName    : " + (r["title"] or "<none>"))
    print("  toolEntityId   : " + str(r["eid"]))
    print("  serverUrl      : " + (r["url"] or "<empty — use documented MCP URL>"))
    print("  authSchemes    : " + (r["schemes"] or "<none>"))
    print("  managedOAuth   : " + str(r["managed"]).lower())
    if r["managed"]:
        # --connector-name for the managed-OAuth connection = the Foundry-brokered app name
        # (x-ms-connector-name, e.g. "foundrygithubmcp"), NOT the toolEntityId objectId.
        print("  connectorName  : " + (r["connector_name"] or "<none — this tile has no brokered connector; use user-entra-token>"))
    print("  userEntraToken : " + str(r["entra"]).lower())
    if r["entra"]:
        print("  audience       : " + (r["audience"] or "<derive from OAuth scope key>"))
    if r["managed"] and r["scopes"]:
        print("  scopes         : " + r["scopes"])
print()
label = {"managed": " supporting managed OAuth", "entra": " supporting user-entra-token", "all": ""}[filt]
print("# " + str(count) + " connector(s)" + label + ".")
'

cat >&2 <<'HINT'
# Managed OAuth (config dialog does NOT ask for an audience):
#   azd ai connection create <name> \
#     --kind remote-tool --auth-type oauth2 \
#     --target <serverUrl-or-documented-MCP-URL> \
#     --connector-name <connectorName> \
#     --metadata type=catalog_MCP \
#     --metadata toolEntityId=<toolEntityId> \
#     --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
#
# User Entra token (config dialog REQUIRES an audience):
#   azd ai connection create <name> \
#     --kind remote-tool --auth-type user-entra-token \
#     --target <serverUrl-or-documented-MCP-URL> \
#     --audience <audience-from-report> \
#     --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
HINT
