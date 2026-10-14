# Access Key Strategy

### 4l. Choose the Access Key Strategy

Inventory key **names only**. Never display or persist values:

```bash
az functionapp keys list --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query "{hostKeys: keys(functionKeys), systemKeys: keys(systemKeys)}" -o json
```

Use the trigger inventory from Step 4j and list per-function key names only for HTTP-triggered source functions:

```bash
az functionapp function keys list --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --function-name <FUNCTION_NAME> --query "keys(@)[?@ != 'id' && @ != 'kind' && @ != 'name' && @ != 'properties' && @ != 'type']" -o json
```

Use `ask_user`:

> The Flex app has new access-key values by default. Existing clients that send source host or function keys must be updated unless those values are copied. Which strategy should this migration use?

1. **Use target-generated keys (recommended)** - keep separate credentials and update clients or workflows before HTTP cutover.
2. **Preserve client keys** - copy source host keys and HTTP-function keys after deployment so existing credentials continue working against the target hostname.

Explain that preservation means the same credentials authorize both apps while they coexist. Record the choice and key names, but no values, in `<UPGRADE_DIR>/upgrade-status.md`.

Don't inventory or copy per-function keys for timer, queue, blob, Event Hubs, Service Bus, Cosmos DB, or other non-HTTP triggers. Those keys don't authorize their trigger invocations.

The `_master` key is target-specific and is never copied because it grants runtime administrative access. System keys are extension-managed and their values can't be explicitly set; inventory their names, let target extensions create new values, and update dependent webhooks such as Event Grid or Durable Functions to use the target system keys.

If key-name inventory fails because `Microsoft.Web/sites/host/listkeys/action` isn't authorized, report the missing permission. The target-generated option remains available; preservation is blocked until the source keys can be read.
