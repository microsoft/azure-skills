# Code Interpreter

Add Code Interpreter directly:

```yaml
tools:
  - type: code_interpreter
```

No project connection is required.

When the service requires files:

```yaml
tools:
  - type: code_interpreter
    container:
      type: auto
      file_ids:
        - <file-id>
```

The object form is service-owned and not validated in detail by azd. Preserve current Foundry REST fields.
