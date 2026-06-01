# BOM Migration — Gradle TOML Version Catalog (`libs.versions.toml`)

OpenRewrite does not yet support TOML version catalogs ([openrewrite/rewrite#4400](https://github.com/openrewrite/rewrite/issues/4400)). Handle manually.

Check for `gradle/libs.versions.toml`. If it exists and contains Azure entries, apply these steps. Always update `build.gradle` / `build.gradle.kts` references in tandem.

Use `TARGET_AZURE_SDK_BOM_VERSION` resolved in the workflow. Do not keep an existing TOML BOM version unless it exactly matches that value.

> 💡 **Tip:** TOML alias `azure-sdk-bom` becomes accessor `libs.azure.sdk.bom` (hyphens→dots). CamelCase `azureSdkBom` becomes `libs.azureSdkBom`. Match the project's existing convention.

## Step 1 — Add or upgrade the BOM

In `gradle/libs.versions.toml`:
```toml
[versions]
azureSdkBom = "{bom_version}"

[libraries]
azure-sdk-bom = { group = "com.azure", name = "azure-sdk-bom", version.ref = "azureSdkBom" }
```

In `build.gradle` (Groovy DSL):
```groovy
implementation enforcedPlatform(libs.azure.sdk.bom)
```

In `build.gradle.kts` (Kotlin DSL):
```kotlin
implementation(enforcedPlatform(libs.azure.sdk.bom))
```

## Step 2 — Remove explicit versions from BOM-managed libraries

For each `com.azure.*` library in `[libraries]` that the BOM manages, drop `version.ref` / `version` and remove orphaned `[versions]` entries.

```toml
# Before
[versions]
azureIdentity = "1.15.0"
[libraries]
azureIdentity = { group = "com.azure", name = "azure-identity", version.ref = "azureIdentity" }

# After
[libraries]
azureIdentity = { group = "com.azure", name = "azure-identity" }
```

## Step 3 — Replace legacy entries with modern equivalents

For each `com.microsoft.azure.*` library: replace `group`/`name` with the modern `com.azure.*` equivalent, drop `version.ref`/`version` if BOM-managed, remove orphaned `[versions]` entries, and update alias references in `build.gradle` and `[bundles]`.

```toml
# Before
[versions]
azureSdk = "1.41.4"
azureStorage = "8.6.6"
[libraries]
azure = { group = "com.microsoft.azure", name = "azure", version.ref = "azureSdk" }
azureStorage = { group = "com.microsoft.azure", name = "azure-storage", version.ref = "azureStorage" }

# After (BOM-managed)
[libraries]
azureResourcemanager = { group = "com.azure.resourcemanager", name = "azure-resourcemanager" }
azureStorageBlob = { group = "com.azure", name = "azure-storage-blob" }
```

Update `build.gradle` and `[bundles]` to use the new aliases.

## TOML patterns to recognise

Libraries may use any of these forms — handle all of them:
```toml
lib = { group = "g", name = "a", version.ref = "v" }
lib = { module = "g:a", version.ref = "v" }
lib = { module = "g:a", version = "1.0" }
lib = { group = "g", name = "a", version = { strictly = "1.0" } }
```
