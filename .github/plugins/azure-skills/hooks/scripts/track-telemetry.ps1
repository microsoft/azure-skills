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

$ErrorActionPreference = "SilentlyContinue"

# Skip telemetry if opted out
if ($env:AZURE_MCP_COLLECT_TELEMETRY -eq "false") {
    Write-Output '{"continue":true}'
    exit 0
}

# Return success and exit
function Write-Success {
    Write-Output '{"continue":true}'
    exit 0
}

# Resolve this script's directory so we can locate bundled skills. In the
# installed plugin, hooks/ and skills/ are siblings under the plugin root, so
# <plugin-root>/skills/<name>/SKILL.md is the skill definition.
$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$skillsDir = Join-Path (Split-Path -Parent (Split-Path -Parent $scriptDir)) 'skills'

# Extract the skill version from a SKILL.md frontmatter (metadata.version).
# Returns $null if the file or version cannot be read.
function Get-SkillVersion {
    param([string]$SkillMdPath)
    if (-not $SkillMdPath) { return $null }
    $SkillMdPath = $SkillMdPath -replace '\\', '/'
    if (-not (Test-Path -LiteralPath $SkillMdPath)) { return $null }
    try {
        $lines = Get-Content -LiteralPath $SkillMdPath -ErrorAction SilentlyContinue
    } catch { return $null }
    $inFrontmatter = $false
    foreach ($line in $lines) {
        if ($line -match '^---\s*$') {
            if (-not $inFrontmatter) { $inFrontmatter = $true; continue }
            else { break }
        }
        if ($inFrontmatter -and $line -match '^\s*version:\s*(.+?)\s*$') {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

# === Main Processing ===

# Read entire stdin at once - hooks send one complete JSON per invocation
try {
    $rawInput = [Console]::In.ReadToEnd()
} catch {
    Write-Success
}

# Return success and exit if no input
if ([string]::IsNullOrWhiteSpace($rawInput)) {
    Write-Success
}

# === STEP 1: Read and parse input ===

# Parse JSON input
try {
    $inputData = $rawInput | ConvertFrom-Json
} catch {
    Write-Success
}

# Extract fields from hook data
# Support Copilot CLI (camelCase), Claude Code (snake_case), and VS Code (snake_case) formats
$toolName = $inputData.toolName
if (-not $toolName) {
    $toolName = $inputData.tool_name
}

$sessionId = $inputData.sessionId
if (-not $sessionId) {
    $sessionId = $inputData.session_id
}

# Get tool arguments (Copilot CLI: toolArgs, Claude Code / VS Code: tool_input)
$toolInput = $inputData.toolArgs
if (-not $toolInput) {
    $toolInput = $inputData.tool_input
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# Detect client name based on input format
# Copilot CLI (>=0.0.421): COPILOT_CLI env var is "1" — primary signal, checked first
# Copilot CLI (<0.0.421):  has "toolArgs" field without "hook_event_name" — backward compat fallback
# VS Code: has hook_event_name AND tool_use_id contains "__vscode" or transcript_path contains "Code"
# Claude Code: has hook_event_name, tool_use_id does NOT contain "__vscode"
$hasHookEventName = $inputData.PSObject.Properties.Name -contains "hook_event_name"
$hasToolArgs = $inputData.PSObject.Properties.Name -contains "toolArgs"
$toolUseId = $inputData.tool_use_id
$transcriptPath = $inputData.transcript_path
$isVscodeToolUseId = $toolUseId -and ($toolUseId -match '__vscode')
# Match path separators around "Code" or "Code - Insiders" to avoid matching "Claude Code"
$isVscodeTranscript = $transcriptPath -and ($transcriptPath -match '[/\\]Code( - Insiders)?[/\\]')

# Copilot CLI check first — env var available since v0.0.421
if ($env:COPILOT_CLI -eq "1") {
    $clientName = "copilot-cli"
} elseif ($hasHookEventName -and ($isVscodeToolUseId -or $isVscodeTranscript)) {
    # Detect VS Code variant from transcript_path
    # Insiders: ...AppData\Roaming\Code - Insiders\User\...
    # Stable:   ...AppData\Roaming\Code\User\...
    if ($transcriptPath -match '[/\\]Code - Insiders[/\\]') {
        $clientName = "Visual Studio Code - Insiders"
    } else {
        $clientName = "Visual Studio Code"
    }
} elseif ($hasHookEventName) {
    $clientName = "claude-code"
} elseif ($hasToolArgs) {
    # Backward compat: old Copilot CLI (<0.0.421) sent toolArgs without hook_event_name
    # Claude Code never sends toolArgs, so this is unambiguous
    $clientName = "copilot-cli"
} else {
    $clientName = "unknown"
}

# Skip if no tool name found in any format
if (-not $toolName) {
    Write-Success
}

# Helper to extract path from tool input (handles 'path', 'filePath', 'file_path')
function Get-ToolInputPath {
    if ($toolInput.path) { return $toolInput.path }
    if ($toolInput.filePath) { return $toolInput.filePath }
    if ($toolInput.file_path) { return $toolInput.file_path }
    return $null
}

# === STEP 2: Determine what to track for azmcp ===

# Azure-skills path patterns per client (used for SKILL.md and file-reference matching)
$pathPatternCopilot = '\.copilot/installed-plugins/azure-skills/azure/skills/'
$pathPatternClaude = '\.claude/plugins/cache/(azure-skills|claude-plugins-official)/azure/[0-9.]+/skills/'
$pathPatternVscodeAgentPlugins = 'agent-plugins/github\.com/microsoft/azure-skills/\.github/plugins/azure-skills/skills/'
$pathPatternAgentsSkills = '\.agents/skills/'

$shouldTrack = $false
$eventType = $null
$skillName = $null
$skillVersion = $null
$azureToolName = $null
$filePath = $null

# Check for skill invocation via 'skill'/'Skill' tool
if ($toolName -eq "skill" -or $toolName -eq "Skill") {
    $skillName = $toolInput.skill
    # Claude Code prefixes skill names with "azure:" (e.g., "azure:azure-prepare")
    # Strip it to get the actual skill name for the allowlist
    if ($skillName -and $skillName.StartsWith("azure:")) {
        $skillName = $skillName.Substring(6)
    }
    if ($skillName) {
        $eventType = "skill_invocation"
        $shouldTrack = $true
        $skillVersion = Get-SkillVersion (Join-Path $skillsDir (Join-Path $skillName 'SKILL.md'))
    }
}

# Check for skill invocation (reading SKILL.md files)
# Copilot CLI: "view", Claude Code: "Read", VS Code: "read_file"
if ($toolName -eq "view" -or $toolName -eq "Read" -or $toolName -eq "read_file") {
    $pathToCheck = Get-ToolInputPath
    if ($pathToCheck) {
        # Normalize path: convert to lowercase, replace backslashes, and squeeze consecutive slashes
        $pathLower = $pathToCheck.ToLower() -replace '\\', '/' -replace '/+', '/'

        # Check for SKILL.md pattern — only match azure-skills paths (see path patterns above)
        $isAzureSkillMd = $false
        if ($pathLower -match "${pathPatternCopilot}[^/]+/skill\.md") {
            $isAzureSkillMd = $true
        } elseif ($pathLower -match "${pathPatternClaude}[^/]+/skill\.md") {
            $isAzureSkillMd = $true
        } elseif ($pathLower -match "${pathPatternVscodeAgentPlugins}[^/]+/skill\.md") {
            $isAzureSkillMd = $true
        } elseif ($pathLower -match "${pathPatternAgentsSkills}[^/]+/skill\.md") {
            $isAzureSkillMd = $true
        }

        if ($isAzureSkillMd) {
            $pathNormalized = $pathToCheck -replace '\\', '/' -replace '/+', '/'
            if ($pathNormalized -match '/skills/([^/]+)/SKILL\.md$') {
                $skillName = $Matches[1]
                $eventType = "skill_invocation"
                $shouldTrack = $true
                $skillVersion = Get-SkillVersion $pathToCheck
            }
        }
    }
}

# Check for Azure MCP tool invocation
# Copilot CLI:  "azure-*" prefix (e.g., azure-documentation)
# Claude Code:  "mcp__plugin_azure_azure__*" prefix (e.g., mcp__plugin_azure_azure__documentation)
# VS Code:      "mcp_azure_mcp_*" prefix (e.g., mcp_azure_mcp_documentation)
if ($toolName) {
    if ($toolName.StartsWith("azure-") -or $toolName.StartsWith("mcp__plugin_azure_azure__") -or $toolName.StartsWith("mcp_azure_mcp_")) {
        $azureToolName = $toolName
        $eventType = "tool_invocation"
        $shouldTrack = $true
    }
}

# Capture file path from any tool input (only track files in azure skills folder)
# Skip if already matched as SKILL.md skill_invocation — SKILL.md is not a valid file-reference
if (-not $filePath -and -not $skillName) {
    $pathToCheck = Get-ToolInputPath
    if ($pathToCheck) {
        # Normalize path for matching: replace backslashes and squeeze consecutive slashes
        $pathLower = $pathToCheck.ToLower() -replace '\\', '/' -replace '/+', '/'

        $matchCopilotSkills = $pathLower -match $pathPatternCopilot
        $matchClaudeSkills = $pathLower -match $pathPatternClaude
        $matchVscodeAgentPlugins = $pathLower -match $pathPatternVscodeAgentPlugins
        $matchAgentsSkills = $pathLower -match $pathPatternAgentsSkills
        if ($matchCopilotSkills -or $matchClaudeSkills -or $matchVscodeAgentPlugins -or $matchAgentsSkills) {
            # Extract relative path after 'skills/'
            $pathNormalized = $pathToCheck -replace '\\', '/' -replace '/+', '/'

            if ($pathNormalized -match '(?:azure/(?:[0-9]+\.[0-9]+\.[0-9]+/)?skills|azure-skills/skills|\.agents/skills)/(.+)$') {
                $filePath = $Matches[1]

                if (-not $shouldTrack) {
                    $shouldTrack = $true
                    $eventType = "reference_file_read"
                    # Resolve the version from the sibling SKILL.md at the root
                    # of the skill folder this reference lives in.
                    $skillNameSeg = ($filePath -split '/')[0]
                    $skillRootAbs = $pathNormalized.Substring(0, $pathNormalized.Length - $filePath.Length)
                    $skillVersion = Get-SkillVersion ("$skillRootAbs$skillNameSeg/SKILL.md")
                }
            }
        }
    }
}

# === STEP 3: Publish event ===

if ($shouldTrack) {
    # Build MCP command arguments
    $mcpArgs = @(
        "server", "plugin-telemetry",
        "--timestamp", $timestamp,
        "--client-name", $clientName
    )

    if ($eventType) { $mcpArgs += "--event-type"; $mcpArgs += $eventType }
    if ($sessionId) { $mcpArgs += "--session-id"; $mcpArgs += $sessionId }
    if ($skillName) { $mcpArgs += "--skill-name"; $mcpArgs += $skillName }
    if ($skillVersion) { $mcpArgs += "--skill-version"; $mcpArgs += $skillVersion }
    if ($azureToolName) { $mcpArgs += "--tool-name"; $mcpArgs += $azureToolName }
    # Convert forward slashes to backslashes for azmcp allowlist compatibility
    if ($filePath) { $mcpArgs += "--file-reference"; $mcpArgs += ($filePath -replace '/', '\') }

    # Publish telemetry via npx
    try {
        & npx -y @azure/mcp@latest @mcpArgs 2>&1 | Out-Null
    } catch { }
}

# Output success to stdout (required by hooks)
Write-Success
