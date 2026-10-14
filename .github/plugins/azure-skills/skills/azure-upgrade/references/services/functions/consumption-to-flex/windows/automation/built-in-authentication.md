# Built-in Authentication

### 4f.auth. Configure Built-in Authentication

Use the safe source summary captured in Step 3c. If `enabled` is `false`, mark this step `skipped — source Easy Auth disabled`.

If authentication is enabled, do not copy the source auth payload wholesale. Provider registrations, client secrets, Key Vault references, audiences, and redirect URIs can be app-specific. Never display or persist provider secrets.

Get the target hostname:

```bash
az functionapp show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query defaultHostName -o tsv
```

For each enabled provider, identify the target callback URI required by that provider. Easy Auth callback URIs generally use `https://<TARGET_HOSTNAME>/.auth/login/<PROVIDER>/callback`, but verify the exact URI against the provider-specific instructions in [Configure built-in authentication](https://learn.microsoft.com/en-us/azure/azure-functions/migration/migrate-plan-consumption-to-flex#configure-built-in-authentication).

Use `ask_user`:

> The source app uses built-in authentication with `<PROVIDERS>`. Authentication registrations and secrets aren't transferred automatically. How should we handle authentication for `<NEW_APP_NAME>`?

1. **Configure and validate now (recommended)** — guide provider-by-provider recreation and verify the target before deployment.
2. **Defer the migration** — leave application code undeployed until authentication is configured and verified.

If deferred, record the enabled providers and target callback URIs in `<UPGRADE_DIR>/upgrade-status.md` without secrets. Mark this step `deferred — built-in authentication not configured` and stop before Step 5. Do not deploy code or run target HTTP validation while the authentication boundary is absent.

If configuring now:

1. For each provider, ask whether to reuse its existing registration or create a target-specific registration. Obtain approval before changing an external identity-provider registration.
2. Guide the user through the provider-specific configuration. Don't request secrets in chat or place them in migration artifacts; have the user configure them directly through the portal, an existing secret-bearing app setting, or a Key Vault reference.
3. Ensure the target callback URI is registered with the provider.
4. Verify the target using the same safe projection used in Step 3c:

   ```bash
   az webapp auth show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "{enabled:enabled,unauthenticatedClientAction:unauthenticatedClientAction,defaultProvider:defaultProvider,tokenStoreEnabled:tokenStoreEnabled,allowedAudiences:allowedAudiences,allowedExternalRedirectUrls:allowedExternalRedirectUrls,isAuthFromFile:isAuthFromFile,providers:{aadClientId:clientId,githubClientId:gitHubClientId,googleClientId:googleClientId,facebookAppId:facebookAppId,twitterConsumerKey:twitterConsumerKey,microsoftAccountClientId:microsoftAccountClientId}}" -o json
   ```

Compare enabled state, unauthenticated behavior, default provider, allowed audiences and redirects, token-store state, and configured provider identifiers. Record intentional differences. Mark the step complete only after the target provider configuration and callback URI are verified.

Do not use an enable-only `az webapp auth update` command as a substitute for recreating the provider configuration.
