# --- azure-skills plugin ---
$pluginPathPatterns = @(
    '\.copilot/installed-plugins/[^/]+/azure/skills/',
    '\.claude/plugins/cache/(azure-skills|claude-plugins-official)/azure/[0-9.]+/skills/',
    '\.cursor/plugins/cache/[^/]+/azure/[^/]+/skills/',
    'agent-plugins/github\.com/microsoft/azure-skills/\.github/plugins/azure-skills/skills/'
)
