# GitHub Copilot Toolset

Requires:

```yaml
harness:
  type: github_copilot_preview
```

Configure built-ins:

```yaml
tools:
  - type: github_copilot_toolset_preview
    defaultConfig:
      enabled: false
    configs:
      - name: filesystem_read
        enabled: true
      - name: filesystem_write
        enabled: false
      - name: shell
        enabled: false
      - name: web
        enabled: true
      - name: subagents
        enabled: true
```

Supported names:

- `filesystem_read`
- `filesystem_write`
- `shell`
- `web`
- `subagents`

`defaultConfig.enabled` sets the default; `configs` overrides individual tools. Duplicate/unknown names, unknown fields, and non-boolean `enabled` values fail before deployment.

The built-in `web` tool is distinct from Foundry `web_search`. Prefer one search path unless the user explicitly needs both.
