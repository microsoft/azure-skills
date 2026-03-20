#!/bin/bash

# Telemetry tracking hook for Azure Copilot Skills
# Reads JSON input from stdin, tracks relevant events, and publishes via MCP

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
    # Try Copilot CLI format (toolArgs) first, then Claude Code format (tool_input)
    value=$(echo "$json" | sed -n "s/.*\"toolArgs\":[[:space:]]*{[^}]*\"$field\":[[:space:]]*\"\([^\"]*\)\".*/\1/p")
    if [ -z "$value" ]; then
        value=$(echo "$json" | sed -n "s/.*\"tool_input\":[[:space:]]*{[^}]*\"$field\":[[:space:]]*\"\([^\"]*\)\".*/\1/p")
    fi
    echo "$value"
}

# Extract path from toolArgs/tool_input (handles both 'path' and 'filePath')
extract_toolargs_path() {
    local json="$1"
    local path_value=""

    # Try Copilot CLI format (toolArgs) first
    path_value=$(echo "$json" | sed -n 's/.*"toolArgs":[[:space:]]*{[^}]*"path":[[:space:]]*"\([^"]*\)".*/\1/p')
    if [ -z "$path_value" ]; then
        path_value=$(echo "$json" | sed -n 's/.*"toolArgs":[[:space:]]*{[^}]*"filePath":[[:space:]]*"\([^"]*\)".*/\1/p')
    fi
    # Fall back to Claude Code format (tool_input)
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
# Support both Copilot CLI (camelCase) and Claude Code (snake_case) formats
toolName=$(extract_json_field "$rawInput" "toolName")
sessionId=$(extract_json_field "$rawInput" "sessionId")

# Fall back to Claude Code snake_case field names
if [ -z "$toolName" ]; then
    toolName=$(extract_json_field "$rawInput" "tool_name")
fi
if [ -z "$sessionId" ]; then
    sessionId=$(extract_json_field "$rawInput" "session_id")
fi

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Detect client type based on which format was used
if echo "$rawInput" | grep -q '"hook_event_name"'; then
    clientType="claude-code"
else
    clientType="copilot-cli"
fi

# Skip if no tool name found in either format
if [ -z "$toolName" ]; then
    return_success
fi

# === STEP 2: Determine what to track for azmcp ===

shouldTrack=false
eventType=""
skillName=""
azureToolName=""
filePath=""

# Check for skill invocation via 'skill'/'Skill' tool
if [ "$toolName" = "skill" ] || [ "$toolName" = "Skill" ]; then
    skillName=$(extract_toolargs_field "$rawInput" "skill")
    if [ -n "$skillName" ]; then
        eventType="skill_invocation"
        shouldTrack=true
    fi
fi

# Check for skill invocation (reading SKILL.md files)
if [ "$toolName" = "view" ]; then
    pathToCheck=$(extract_toolargs_path "$rawInput")
    if [ -n "$pathToCheck" ]; then
        # Normalize path: convert to lowercase, replace backslashes, and squeeze consecutive slashes
        pathLower=$(echo "$pathToCheck" | tr '[:upper:]' '[:lower:]' | tr '\\' '/' | sed 's|//*|/|g')

        # Check for SKILL.md pattern (Copilot: .copilot/...skills/; Claude: .claude/...skills/)
        if [[ "$pathLower" == *".copilot"*"skills"*"/skill.md" ]] || [[ "$pathLower" == *".claude"*"skills"*"/skill.md" ]]; then
            # Normalize path and extract skill name using regex
            pathNormalized=$(echo "$pathToCheck" | tr '\\' '/' | sed 's|//*|/|g')
            if [[ "$pathNormalized" =~ /skills/([^/]+)/SKILL\.md$ ]]; then
                skillName="${BASH_REMATCH[1]}"
                eventType="skill_invocation"
                shouldTrack=true
            fi
        fi
    fi
fi

# Check for Azure MCP tool invocation
# Copilot CLI: "mcp_azure_*" or "azure-*" prefixes
# Claude Code: "mcp__plugin_azure_azure__*" prefix (double underscores)
if [ -n "$toolName" ]; then
    if [[ "$toolName" == mcp_azure_* ]] || [[ "$toolName" == azure-* ]] || [[ "$toolName" == mcp__plugin_azure_azure__* ]]; then
        azureToolName="$toolName"
        eventType="tool_invocation"
        shouldTrack=true
    fi
fi

# Capture file path from any tool input (only track files in azure\skills folder)
# Check both 'path' and 'filePath' properties
if [ -z "$filePath" ]; then
    pathToCheck=$(extract_toolargs_path "$rawInput")
    if [ -n "$pathToCheck" ]; then
        # Normalize path for matching: replace backslashes and squeeze consecutive slashes
        pathLower=$(echo "$pathToCheck" | tr '[:upper:]' '[:lower:]' | tr '\\' '/' | sed 's|//*|/|g')

        # Check if path matches azure skills folder structure
        # Copilot: .copilot/installed-plugins/azure-skills/azure/skills/...
        # Claude:  .claude/plugins/cache/azure-skills/azure/<version>/skills/...
        if [[ "$pathLower" == *".copilot"*"installed-plugins"*"azure-skills"*"azure"*"skills"* ]] || [[ "$pathLower" == *".claude"*"plugins"*"cache"*"azure-skills"*"azure"*"skills"* ]]; then
            # Extract relative path after 'azure/skills/' or 'azure/<version>/skills/'
            pathNormalized=$(echo "$pathToCheck" | tr '\\' '/' | sed 's|//*|/|g')

            if [[ "$pathNormalized" =~ azure/([0-9]+\.[0-9]+\.[0-9]+/)?skills/(.+)$ ]]; then
                filePath="${BASH_REMATCH[2]}"

                if [ "$shouldTrack" = false ]; then
                    shouldTrack=true
                    eventType="reference_file_read"
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
        "--client-type" "$clientType"
    )

    [ -n "$eventType" ] && mcpArgs+=("--event-type" "$eventType")
    [ -n "$sessionId" ] && mcpArgs+=("--session-id" "$sessionId")
    [ -n "$skillName" ] && mcpArgs+=("--skill-name" "$skillName")
    [ -n "$azureToolName" ] && mcpArgs+=("--tool-name" "$azureToolName")
    # Convert forward slashes to backslashes for azmcp allowlist compatibility
    [ -n "$filePath" ] && mcpArgs+=("--file-reference" "$(echo "$filePath" | tr '/' '\\')")

    # Publish telemetry via npx
    npx -y @azure/mcp@latest "${mcpArgs[@]}" >/dev/null 2>&1 || true
fi

# Output success to stdout (required by hooks)
return_success
