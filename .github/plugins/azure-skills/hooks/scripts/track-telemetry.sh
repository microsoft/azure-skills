#!/bin/bash

# Telemetry tracking hook for Azure Copilot Skills
# Reads JSON input from stdin, tracks relevant events, and publishes via MCP
#
# === Client Format Reference ===
#
# Copilot CLI:
#   - Field names:    camelCase (toolName, sessionId, toolArgs)
#   - Tool names:     lowercase (skill, view)
#   - MCP prefix:     azure-<command>  (e.g., azure-documentation)
#   - Skill prefix:   none (skill name as-is)
#   - Detection:      COPILOT_CLI env var is "1" (>=0.0.421); fallback: "toolArgs" without "hook_event_name" (<0.0.421)
#
# Claude Code:
#   - Field names:    snake_case (tool_name, session_id, tool_input, hook_event_name)
#   - Tool names:     PascalCase (Skill, Read, Edit)
#   - MCP prefix:     mcp__plugin_azure_azure__<command>  (double underscores)
#   - Skill prefix:   azure:<skill-name>  (e.g., azure:azure-prepare)
#   - Detection:      has "hook_event_name", tool_use_id does NOT contain "__vscode"
#
# VS Code:
#   - Field names:    snake_case (tool_name, session_id, tool_input, hook_event_name)
#   - Tool names:     snake_case (read_file, replace_string_in_file)
#   - MCP prefix:     mcp_azure_mcp_<command>  (e.g., mcp_azure_mcp_documentation)
#   - Skill paths:    .vscode/agent-plugins/github.com/microsoft/azure-skills/.github/plugins/azure-skills/skills/<name>/SKILL.md          (VS Code)
#                     .vscode-insiders/agent-plugins/github.com/microsoft/azure-skills/.github/plugins/azure-skills/skills/<name>/SKILL.md (VS Code Insiders)
#                     .agents/skills/<name>/SKILL.md
#   - Detection:      has "hook_event_name", tool_use_id contains "__vscode"
#                     or transcript_path contains "Code"
#   - Client name:    "Visual Studio Code" (stable) or "Visual Studio Code - Insiders"
#                     derived from transcript_path (e.g., .../Code - Insiders/User/...)
#   - Note:           Skills under .agents/skills/ are tracked as "Visual Studio Code" but
#                     transcript_path may be absent, so stable vs Insiders can only be
#                     distinguished when skills are called from agent-plugins (which
#                     includes transcript_path)
#
# === Event Types ===
#
# 1. skill_invocation
#    - Triggered when: the "skill"/"Skill" tool is called with a skill name,
#      OR a SKILL.md file is read from a recognized azure-skills path
#    - Tracked fields: --skill-name <name>, --skill-version <version>
#
# 2. tool_invocation
#    - Triggered when: a tool matching an Azure MCP prefix is called
#      (azure-*, mcp__plugin_azure_azure__*, mcp_azure_mcp_*)
#    - Tracked field: --tool-name <toolName>
#
# 3. reference_file_read
#    - Triggered when: a file read tool (view/Read/read_file) targets a file
#      inside a recognized azure-skills path that is NOT a SKILL.md
#    - These are the reference/instruction files that skills bundle alongside
#      SKILL.md (e.g., recipes, templates, requirement docs)
#    - Tracked fields: --file-reference <relative-path-after-skills/>,
#      --skill-version <version>
#
# === Skill Version ===
#
# The skill version is read from the SKILL.md frontmatter (metadata.version),
# which the build stamps at package time. It is resolved as follows:
#   - skill/Skill tool call: locate SKILL.md relative to this script's plugin
#     root ("<plugin-root>/skills/<name>/SKILL.md")
#   - SKILL.md read:          read the version from the SKILL.md being read
#   - reference_file_read:    read the version from the sibling SKILL.md at the
#                             root of the skill folder the reference lives in
#    - Example: azure-validate/references/recipes/azd/README.md
#
# === Reference File Detection ===
#
# When a file read tool is invoked (Copilot CLI: "view", Claude Code: "Read",
# VS Code: "read_file"), the script extracts the file path from the tool input
# and checks if it falls within a recognized azure-skills folder:
#
#   Path field lookup order:
#     - toolArgs.path / toolArgs.filePath       (Copilot CLI)
#     - tool_input.filePath / tool_input.file_path / tool_input.path  (Claude Code / VS Code)
#
#   Recognized azure-skills install paths:
#     - .copilot/installed-plugins/azure-skills/azure/skills/...
#     - .claude/plugins/cache/azure-skills/azure/<version>/skills/...
#     - .claude/plugins/cache/claude-plugins-official/azure/<version>/skills/...
#     - .vscode/agent-plugins/github.com/microsoft/azure-skills/.github/plugins/azure-skills/skills/...
#     - .agents/skills/...
#
#   If the path matches AND is not a SKILL.md file, the relative path after
#   "skills/" is extracted and emitted as a reference_file_read event.
#   SKILL.md reads are tracked as skill_invocation instead (not double-counted).

set +e  # Don't exit on errors - fail silently for privacy

# Skip telemetry if opted out
if [ "${AZURE_MCP_COLLECT_TELEMETRY}" = "false" ]; then
    echo '{"continue":true}'
    exit 0
fi

# Return success and exit
return_success() {
    echo '{"continue":true}'
    exit 0
}

# Resolve this script's directory so we can locate bundled skills. In the
# installed plugin, hooks/ and skills/ are siblings under the plugin root, so
# <script-dir>/../../skills/<name>/SKILL.md is the skill definition.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
SKILLS_DIR="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd)/skills"

# Extract the skill version from a SKILL.md frontmatter (metadata.version).
# Prints nothing if the file or version cannot be read.
get_skill_version() {
    local skillMdPath="$1"
    [ -n "$skillMdPath" ] || return 0
    # Normalize backslashes so Windows-style paths are readable
    skillMdPath="$(echo "$skillMdPath" | tr '\\' '/')"
    [ -f "$skillMdPath" ] || return 0
    # Read the frontmatter block (between the first two --- lines) and pull the
    # version value, stripping surrounding quotes and whitespace.
    sed -n '/^---[[:space:]]*$/,/^---[[:space:]]*$/p' "$skillMdPath" 2>/dev/null \
        | grep -E '^[[:space:]]*version:[[:space:]]*' \
        | head -1 \
        | sed -E 's/^[[:space:]]*version:[[:space:]]*//; s/^["'"'"']//; s/["'"'"'][[:space:]]*$//; s/[[:space:]]*$//'
}

# === JSON Parsing Functions (using sed - portable across platforms) ===

# Extract simple string field from JSON
extract_json_field() {
    local json="$1"
    local field="$2"
    echo "$json" | sed -n "s/.*\"$field\":[[:space:]]*\"\([^\"]*\)\".*/\1/p"
}

# Extract nested field from toolArgs/tool_input (e.g., toolArgs.skill or tool_input.skill)
extract_toolargs_field() {
    local json="$1"
    local field="$2"
    local value=""
    # Try Copilot CLI format (toolArgs) first, then Claude Code / VS Code format (tool_input)
    value=$(echo "$json" | sed -n "s/.*\"toolArgs\":[[:space:]]*{[^}]*\"$field\":[[:space:]]*\"\([^\"]*\)\".*/\1/p")
    if [ -z "$value" ]; then
        value=$(echo "$json" | sed -n "s/.*\"tool_input\":[[:space:]]*{[^}]*\"$field\":[[:space:]]*\"\([^\"]*\)\".*/\1/p")
    fi
    echo "$value"
}

# Extract path from toolArgs/tool_input (handles 'path', 'filePath', 'file_path')
extract_toolargs_path() {
    local json="$1"
    local path_value=""

    # Try Copilot CLI format (toolArgs) first
    path_value=$(echo "$json" | sed -n 's/.*"toolArgs":[[:space:]]*{[^}]*"path":[[:space:]]*"\([^"]*\)".*/\1/p')
    if [ -z "$path_value" ]; then
        path_value=$(echo "$json" | sed -n 's/.*"toolArgs":[[:space:]]*{[^}]*"filePath":[[:space:]]*"\([^"]*\)".*/\1/p')
    fi
    # Fall back to Claude Code / VS Code format (tool_input)
    if [ -z "$path_value" ]; then
        path_value=$(echo "$json" | sed -n 's/.*"tool_input":[[:space:]]*{[^}]*"filePath":[[:space:]]*"\([^"]*\)".*/\1/p')
    fi
    if [ -z "$path_value" ]; then
        path_value=$(echo "$json" | sed -n 's/.*"tool_input":[[:space:]]*{[^}]*"file_path":[[:space:]]*"\([^"]*\)".*/\1/p')
    fi
    if [ -z "$path_value" ]; then
        path_value=$(echo "$json" | sed -n 's/.*"tool_input":[[:space:]]*{[^}]*"path":[[:space:]]*"\([^"]*\)".*/\1/p')
    fi

    echo "$path_value"
}

# === Main Processing ===

# Check if stdin has data
if [ -t 0 ]; then
    return_success
fi

# Read entire stdin at once - hooks send one complete JSON per invocation
rawInput=$(cat)

# Return success and exit if no input
if [ -z "$rawInput" ]; then
    return_success
fi

# === STEP 1: Read and parse input ===

# Extract fields from hook data
# Support Copilot CLI (camelCase), Claude Code (snake_case), and VS Code (snake_case) formats
toolName=$(extract_json_field "$rawInput" "toolName")
sessionId=$(extract_json_field "$rawInput" "sessionId")

# Fall back to Claude Code / VS Code snake_case field names
if [ -z "$toolName" ]; then
    toolName=$(extract_json_field "$rawInput" "tool_name")
fi
if [ -z "$sessionId" ]; then
    sessionId=$(extract_json_field "$rawInput" "session_id")
fi

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Detect client name based on input format
# Copilot CLI (>=0.0.421): COPILOT_CLI env var is "1" — primary signal, checked first
# Copilot CLI (<0.0.421):  has "toolArgs" field without "hook_event_name" — backward compat fallback
# VS Code: has hook_event_name AND tool_use_id contains "__vscode" or transcript_path contains "Code"
# Claude Code: has hook_event_name, tool_use_id does NOT contain "__vscode"
if [ "$COPILOT_CLI" = "1" ]; then
    clientName="copilot-cli"
elif echo "$rawInput" | grep -q '"hook_event_name"'; then
    toolUseId=$(extract_json_field "$rawInput" "tool_use_id")
    transcriptPath=$(extract_json_field "$rawInput" "transcript_path")
    # Normalize backslashes to forward slashes for consistent matching
    transcriptPathNorm=$(echo "$transcriptPath" | tr '\\' '/')
    # Match path separators around "Code" or "Code - Insiders" to avoid matching "Claude Code"
    if [[ "$toolUseId" == *"__vscode"* ]] || [[ "$transcriptPathNorm" == */Code/* ]] || [[ "$transcriptPathNorm" == */Code\ -\ Insiders/* ]]; then
        # Detect VS Code variant from transcript_path
        # Insiders: ...AppData/Roaming/Code - Insiders/User/...
        # Stable:   ...AppData/Roaming/Code/User/...
        if [[ "$transcriptPathNorm" == */Code\ -\ Insiders/* ]]; then
            clientName="Visual Studio Code - Insiders"
        else
            clientName="Visual Studio Code"
        fi
    else
        clientName="claude-code"
    fi
elif echo "$rawInput" | grep -q '"toolArgs"'; then
    # Backward compat: old Copilot CLI (<0.0.421) sent toolArgs without hook_event_name
    # Claude Code never sends toolArgs, so this is unambiguous
    clientName="copilot-cli"
else
    clientName="unknown"
fi

# Skip if no tool name found in any format
if [ -z "$toolName" ]; then
    return_success
fi

# === STEP 2: Determine what to track for azmcp ===

# Check if a path matches any known azure-skills folder structure
# Returns 0 (true) if matched, 1 (false) otherwise
is_azure_skills_path() {
    local p="$1"
    [[ "$p" == *".copilot/installed-plugins/azure-skills/azure/skills/"* ]] && return 0
    [[ "$p" == *".claude/plugins/cache/azure-skills/azure/"*"/skills/"* ]] && return 0
    [[ "$p" == *".claude/plugins/cache/claude-plugins-official/azure/"*"/skills/"* ]] && return 0
    [[ "$p" == *"agent-plugins/github.com/microsoft/azure-skills/.github/plugins/azure-skills/skills/"* ]] && return 0
    [[ "$p" == *".agents/skills/"* ]] && return 0
    return 1
}

shouldTrack=false
eventType=""
skillName=""
skillVersion=""
azureToolName=""
filePath=""

# Check for skill invocation via 'skill'/'Skill' tool
if [ "$toolName" = "skill" ] || [ "$toolName" = "Skill" ]; then
    skillName=$(extract_toolargs_field "$rawInput" "skill")
    # Claude Code prefixes skill names with "azure:" (e.g., "azure:azure-prepare")
    # Strip it to get the actual skill name for the allowlist
    skillName="${skillName#azure:}"
    if [ -n "$skillName" ]; then
        eventType="skill_invocation"
        shouldTrack=true
        skillVersion=$(get_skill_version "$SKILLS_DIR/$skillName/SKILL.md")
    fi
fi

# Check for skill invocation (reading SKILL.md files)
# Copilot CLI: "view", Claude Code: "Read", VS Code: "read_file"
if [ "$toolName" = "view" ] || [ "$toolName" = "Read" ] || [ "$toolName" = "read_file" ]; then
    pathToCheck=$(extract_toolargs_path "$rawInput")
    if [ -n "$pathToCheck" ]; then
        # Normalize path: convert to lowercase, replace backslashes, and squeeze consecutive slashes
        pathLower=$(echo "$pathToCheck" | tr '[:upper:]' '[:lower:]' | tr '\\' '/' | sed 's|//*|/|g')

        # Check for SKILL.md pattern — only match azure-skills paths
        if is_azure_skills_path "$pathLower" && [[ "$pathLower" == *"/skill.md" ]]; then
            pathNormalized=$(echo "$pathToCheck" | tr '\\' '/' | sed 's|//*|/|g')
            if [[ "$pathNormalized" =~ /skills/([^/]+)/SKILL\.md$ ]]; then
                skillName="${BASH_REMATCH[1]}"
                eventType="skill_invocation"
                shouldTrack=true
                skillVersion=$(get_skill_version "$pathToCheck")
            fi
        fi
    fi
fi

# Check for Azure MCP tool invocation
# Copilot CLI:  "azure-*" prefix (e.g., azure-documentation)
# Claude Code:  "mcp__plugin_azure_azure__*" prefix (e.g., mcp__plugin_azure_azure__documentation)
# VS Code:      "mcp_azure_mcp_*" prefix (e.g., mcp_azure_mcp_documentation)
if [ -n "$toolName" ]; then
    if [[ "$toolName" == azure-* ]] || [[ "$toolName" == mcp__plugin_azure_azure__* ]] || [[ "$toolName" == mcp_azure_mcp_* ]]; then
        azureToolName="$toolName"
        eventType="tool_invocation"
        shouldTrack=true
    fi
fi

# Capture file path from any tool input (only track files in azure skills folder)
# Skip if already matched as SKILL.md skill_invocation — SKILL.md is not a valid file-reference
if [ -z "$filePath" ] && [ -z "$skillName" ]; then
    pathToCheck=$(extract_toolargs_path "$rawInput")
    if [ -n "$pathToCheck" ]; then
        # Normalize path for matching: replace backslashes and squeeze consecutive slashes
        pathLower=$(echo "$pathToCheck" | tr '[:upper:]' '[:lower:]' | tr '\\' '/' | sed 's|//*|/|g')

        # Check if path matches azure skills folder structure
        if is_azure_skills_path "$pathLower"; then
            # Extract relative path after 'skills/'
            pathNormalized=$(echo "$pathToCheck" | tr '\\' '/' | sed 's|//*|/|g')

            if [[ "$pathNormalized" =~ (azure/([0-9]+\.[0-9]+\.[0-9]+/)?skills|azure-skills/skills|\.agents/skills)/(.+)$ ]]; then
                filePath="${BASH_REMATCH[3]}"

                if [ "$shouldTrack" = false ]; then
                    shouldTrack=true
                    eventType="reference_file_read"
                    # Resolve the version from the sibling SKILL.md at the root
                    # of the skill folder this reference lives in. Strip the
                    # relative suffix by length (literal removal) so glob
                    # metacharacters in the path can't corrupt the result.
                    skillNameSeg="${filePath%%/*}"
                    skillRootAbs="${pathNormalized:0:${#pathNormalized}-${#filePath}}"
                    skillVersion=$(get_skill_version "${skillRootAbs}${skillNameSeg}/SKILL.md")
                fi
            fi
        fi
    fi
fi

# === STEP 3: Publish event via azmcp ===

if [ "$shouldTrack" = true ]; then
    # Build MCP command arguments (using array for proper quoting)
    mcpArgs=(
        "server" "plugin-telemetry"
        "--timestamp" "$timestamp"
        "--client-name" "$clientName"
    )

    [ -n "$eventType" ] && mcpArgs+=("--event-type" "$eventType")
    [ -n "$sessionId" ] && mcpArgs+=("--session-id" "$sessionId")
    [ -n "$skillName" ] && mcpArgs+=("--skill-name" "$skillName")
    [ -n "$skillVersion" ] && mcpArgs+=("--skill-version" "$skillVersion")
    [ -n "$azureToolName" ] && mcpArgs+=("--tool-name" "$azureToolName")
    # Convert forward slashes to backslashes for azmcp allowlist compatibility
    [ -n "$filePath" ] && mcpArgs+=("--file-reference" "$(echo "$filePath" | tr '/' '\\')")

    # Publish telemetry via npx
    npx -y @azure/mcp@latest "${mcpArgs[@]}" >/dev/null 2>&1 || true
fi

# Output success to stdout (required by hooks)
return_success

