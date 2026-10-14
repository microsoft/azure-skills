# Cleanup and Rollback

## Step 7: Cleanup (Optional)

Read the outcome and deferred work from `<UPGRADE_DIR>/upgrade-status.md`. Do not offer source deletion unless the outcome is `production cutover complete`.

Before offering deletion, verify and record that:

1. all applicable production HTTP traffic, clients, key-dependent workflows, DNS, and custom domains use the target;
2. every applicable production trigger has completed the source-first cutover and target validation;
3. no production-readiness item remains deferred;
4. the source no longer processes production workloads.

If any condition is not met, do not present a deletion prompt. Record cleanup as `skipped — production cutover incomplete` or `deferred — source retained for later cleanup`, matching the user's intent.

Only after all conditions pass, use `ask_user` immediately before deletion:

> Production cutover is complete and source app `<SOURCE_APP_NAME>` is no longer processing production workloads. May I permanently delete it? This is irreversible and removes the rollback app.

Run only after that explicit approval:

```bash
az functionapp delete --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP>
```

> 💡 No rush. The Consumption plan only charges for actual usage, so keeping the old app (with triggers disabled) costs very little. We recommend keeping it for a few days/weeks.

---

## Rollback

For a function-specific production cutover, use the rollback transaction already authorized in [Step 6](validation-and-cutover.md#path-b-production-cutover): disable and verify the target function first, then re-enable and verify the source function.

If the source app was previously stopped, use `ask_user` immediately before restarting it:

> May I restart source app `<SOURCE_APP_NAME>` in resource group `<SOURCE_RESOURCE_GROUP>` to restore processing?

Run the source command only after explicit approval:

```bash
az functionapp start --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP>
```

After the source app or affected source functions are running, reverse each routing change made during cutover:

1. If clients or producers were redirected to new queues, topics, containers, consumer groups, event subscriptions, or endpoints, describe the exact reversal and obtain approval before redirecting them to the original resources.
2. If HTTP clients were changed to use the Flex app URL, restore the original source-app URL.
3. If DNS or custom-domain mappings were changed, use `ask_user` immediately before reverting each mapping to the source app.
4. Verify that the source receives HTTP traffic and that each restored trigger completes a normal execution cycle. Keep the corresponding target functions disabled until rollback validation succeeds to avoid duplicate processing.

Do not delete target resources or target-specific dependencies merely because traffic has been rolled back. Retain them for diagnosis or a later retry unless the user separately approves their deletion.

Deleting the new Flex app does not modify the source app, but still requires confirmation under the global destructive-action policy:

```bash
az functionapp delete --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>
```
