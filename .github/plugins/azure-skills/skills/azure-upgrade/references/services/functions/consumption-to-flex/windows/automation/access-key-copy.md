# Access Key Copy

### 5a. Apply the Access Key Strategy

Run only after Step 5 verifies that all target functions synchronized. If Step 4l selected target-generated keys, mark this step `skipped - target-generated keys selected` and record that key-dependent clients must be updated before HTTP cutover.

If preservation was selected, process only HTTP-triggered functions from the verified Step 4j trigger inventory. Match those source and target functions by exact name. For a keyed source HTTP function without an exact target match, ask whether it was removed or renamed. Skip removed functions with a recorded reason; require an explicit source-to-target name mapping for renamed functions.

Fetch key values only into process memory. For each source host key, run:

```bash
az functionapp keys set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --key-type functionKeys --key-name <KEY_NAME> --key-value <KEY_VALUE> --output none --only-show-errors
```

For each key returned by `az functionapp function keys list` for each mapped HTTP function, run:

```bash
az functionapp function keys set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --function-name <TARGET_FUNCTION_NAME> --key-name <KEY_NAME> --key-value <KEY_VALUE> --output none --only-show-errors
```

Use `jq` in Bash and `ConvertFrom-Json` in PowerShell to enumerate the in-memory `functionKeys` object and per-function key properties. Exclude the per-function metadata fields `id`, `kind`, `name`, `properties`, and `type`. Check `$LASTEXITCODE` after every native command in PowerShell. Clear every JSON object, key value, and derived row in `trap`/`finally`.

> ⚠️ `--key-value` briefly exposes the value in the Azure CLI child process arguments. Run only in a trusted terminal, never enable shell tracing or CLI debug output, and use `--output none --only-show-errors`. Never write keys to migration artifacts or temporary files.

Reruns are idempotent: setting the same name and value overwrites the matching target key. Preserve target-only keys; don't delete anything.

After all writes, re-list source and target host keys and HTTP-function keys into memory and compare every selected name and value. Report only counts and pass/fail results. On any mismatch or CLI failure, clear variables, mark Step 5a blocked, and don't begin HTTP validation or cutover.

List target system-key names after deployment and record which webhook integrations need their target-generated values. Never copy or display the `_master` key or system-key values.
