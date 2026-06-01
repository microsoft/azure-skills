# BOM Migration — Validation Checklist

After BOM migration, verify:

- [ ] Project compiles successfully.
- [ ] No legacy `com.microsoft.azure.*` dependencies remain anywhere (pom.xml, build.gradle, TOML, settings.gradle).
- [ ] BOM-managed Azure libraries have **no** explicit version (no `<version>` tag, no version string, no `version.ref`, no `.versionRef()`).
- [ ] Re-resolve the latest stable `azure-sdk-bom` from the Azure SDK for Java source of truth and confirm the plan guideline `TARGET_AZURE_SDK_BOM_VERSION` matches it exactly.
- [ ] Every BOM version in the migrated project equals `TARGET_AZURE_SDK_BOM_VERSION`; no BOM version was copied from the original project, examples, prior plans, or model memory.
- [ ] No stale `azure-sdk-bom` version remains.

## Additional checks for TOML version catalog projects

- [ ] No orphaned entries in `[versions]` (every version key must be referenced by at least one library or plugin).
- [ ] `[bundles]` aliases match current `[libraries]` aliases (no stale references).
- [ ] `build.gradle` uses `libs.<alias>` references — no raw `"group:artifact:version"` strings for Azure libraries.

## Additional checks for programmatic settings.gradle catalog projects

- [ ] No orphaned `version(...)` calls (every version must be referenced by at least one `library` or `plugin` entry).
- [ ] `bundle(...)` aliases match current `library(...)` aliases (no stale references).
- [ ] `build.gradle` uses `libs.<alias>` references — no raw `"group:artifact:version"` strings for Azure libraries.
