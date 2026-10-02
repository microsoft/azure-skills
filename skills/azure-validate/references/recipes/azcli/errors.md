# AZCLI Validation Errors

| Error | Fix |
|-------|-----|
| `AADSTS700082: Token expired` | `az login` |
| `Please run 'az login'` | `az login` |
| `AADSTS50076: MFA required` | `az login --use-device-code` |
| `AuthorizationFailed` | Request Contributor role |
| `npm ci` fails with `missing: package-lock.json` | Run `npm install --package-lock-only` in the service directory before building |
| `Template validation failed` | Check Bicep syntax |

## Debug

```bash
az <command> --verbose --debug
```
