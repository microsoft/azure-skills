#!/usr/bin/env bash
# Copilot app entry preflight.
# Detects AI_AGENT=github_copilot_app_agent and, only in that environment,
# silently installs Copilot app-specific add-ons. Currently, the add-on is
# microsoft-foundry. Discovery and installation failures are non-blocking.

set -uo pipefail

PLUGIN_NAME="microsoft-foundry"
PLUGIN_SPEC="microsoft-foundry@awesome-copilot"

warn() {
  echo "[WARN] $1" >&2
}

if [ "${AI_AGENT:-}" != "github_copilot_app_agent" ]; then
  exit 0
fi

if ! command -v copilot >/dev/null 2>&1; then
  warn "GitHub Copilot CLI is unavailable; skipped $PLUGIN_NAME plugin installation."
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  warn "python3 is unavailable; could not inspect installed Copilot plugins."
  exit 0
fi

plugins_json="$(copilot plugins list --kind plugin --json 2>&1)"
list_exit=$?
if [ "$list_exit" -ne 0 ]; then
  warn "Could not inspect installed Copilot plugins: $plugins_json"
  exit 0
fi

python3 -c '
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    raise SystemExit(2)

plugins = data.get("plugins", []) if isinstance(data, dict) else []
name = sys.argv[1]
raise SystemExit(
    0
    if any(isinstance(plugin, dict) and plugin.get("name") == name for plugin in plugins)
    else 1
)
' "$PLUGIN_NAME" <<<"$plugins_json"
match_exit=$?

case "$match_exit" in
  0)
    exit 0
    ;;
  1)
    ;;
  *)
    warn "Could not parse installed Copilot plugins; skipped $PLUGIN_NAME plugin installation."
    exit 0
    ;;
esac

install_output="$(copilot plugins install "$PLUGIN_SPEC" 2>&1)"
install_exit=$?
if [ "$install_exit" -ne 0 ]; then
  warn "Could not install $PLUGIN_SPEC: $install_output"
fi

exit 0
