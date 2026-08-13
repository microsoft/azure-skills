#!/usr/bin/env bash
# Copilot app entry preflight.
# Detects AI_AGENT=github_copilot_app_agent, locates either a PATH-visible
# Copilot CLI or the CLI bundled by github-copilot-sdk, and reports whether the
# microsoft-foundry plugin needs installation. This script is read-only.
#
# Output: [OK], [WARN], or [ACTION].
# Exit code: 1 only when plugin installation is required; otherwise 0.

set -uo pipefail

PLUGIN_NAME="microsoft-foundry"
PLUGIN_SPEC="microsoft-foundry@awesome-copilot"
COPILOT_CLI=""

note_ok()     { echo "[OK] $1"; }
note_warn()   { echo "[WARN] $1"; }
note_action() { echo "[ACTION] $1"; }

# Pick the highest semantic version under github-copilot-sdk/cli/<version>/.
# An unsuffixed version sorts after the same version with a numeric suffix,
# matching the SDK locator used by the Copilot app installer.
pick_highest_cli() {
  local root="$1"
  local executable="$2"
  local dir name candidate
  local major minor patch suffix
  local best_major=-1 best_minor=-1 best_patch=-1 best_suffix=-1
  local best=""

  [ -d "$root" ] || return 1

  for dir in "$root"/*; do
    [ -d "$dir" ] || continue
    name="${dir##*/}"
    if [[ ! "$name" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)(-([0-9]+))?$ ]]; then
      continue
    fi

    major=$((10#${BASH_REMATCH[1]}))
    minor=$((10#${BASH_REMATCH[2]}))
    patch=$((10#${BASH_REMATCH[3]}))
    if [ -n "${BASH_REMATCH[5]:-}" ]; then
      suffix=$((10#${BASH_REMATCH[5]}))
    else
      suffix=9223372036854775807
    fi

    candidate="$dir/$executable"
    [ -x "$candidate" ] || continue

    if (( major > best_major ||
          (major == best_major && minor > best_minor) ||
          (major == best_major && minor == best_minor && patch > best_patch) ||
          (major == best_major && minor == best_minor && patch == best_patch && suffix > best_suffix) )); then
      best="$candidate"
      best_major=$major
      best_minor=$minor
      best_patch=$patch
      best_suffix=$suffix
    fi
  done

  [ -n "$best" ] || return 1
  COPILOT_CLI="$best"
  return 0
}

locate_copilot_cli() {
  local platform data_root cache_root

  if command -v copilot >/dev/null 2>&1; then
    COPILOT_CLI="$(command -v copilot)"
    return 0
  fi

  if [ -n "${COPILOT_CLI_PATH:-}" ] && [ -x "$COPILOT_CLI_PATH" ]; then
    COPILOT_CLI="$COPILOT_CLI_PATH"
    return 0
  fi

  platform="$(uname -s 2>/dev/null || echo Linux)"
  case "$platform" in
    Darwin)
      data_root="${HOME:-}/Library/Application Support/github-copilot-sdk/cli"
      cache_root="${HOME:-}/Library/Caches/github-copilot-sdk/cli"
      ;;
    *)
      data_root="${XDG_DATA_HOME:-${HOME:-}/.local/share}/github-copilot-sdk/cli"
      if [ -n "${XDG_CACHE_HOME:-}" ] && [[ "$XDG_CACHE_HOME" = /* ]]; then
        cache_root="$XDG_CACHE_HOME/github-copilot-sdk/cli"
      else
        cache_root="${HOME:-}/.cache/github-copilot-sdk/cli"
      fi
      ;;
  esac

  if pick_highest_cli "$data_root" "copilot"; then
    return 0
  fi

  if [ -n "${COPILOT_CLI_EXTRACT_DIR:-}" ] && [ -x "$COPILOT_CLI_EXTRACT_DIR/copilot" ]; then
    COPILOT_CLI="$COPILOT_CLI_EXTRACT_DIR/copilot"
    return 0
  fi

  pick_highest_cli "$cache_root" "copilot"
}

if [ "${AI_AGENT:-}" != "github_copilot_app_agent" ]; then
  note_ok "GitHub Copilot app not detected; no plugin check needed."
  exit 0
fi

if ! locate_copilot_cli; then
  note_warn "Could not locate the GitHub Copilot CLI on PATH or in github-copilot-sdk data/cache locations; could not inspect the $PLUGIN_NAME plugin."
  exit 0
fi

plugins_json="$("$COPILOT_CLI" plugins list --kind plugin --json 2>&1)"
list_exit=$?
if [ "$list_exit" -ne 0 ]; then
  note_warn "Could not inspect installed Copilot plugins: $plugins_json"
  exit 0
fi

# The CLI guarantees JSON on a successful --json invocation. Match the fixed
# plugin name as a complete JSON string value, allowing arbitrary whitespace,
# so this check needs no Python, jq, or other JSON-parser dependency.
plugin_name_pattern="\"name\"[[:space:]]*:[[:space:]]*\"${PLUGIN_NAME}\""
if [[ "$plugins_json" =~ $plugin_name_pattern ]]; then
  note_ok "Copilot plugin '$PLUGIN_NAME' is installed."
  exit 0
fi

printf -v copilot_command '%q' "$COPILOT_CLI"
note_action "Copilot plugin '$PLUGIN_NAME' is missing. Run: $copilot_command plugins install $PLUGIN_SPEC"
exit 1
