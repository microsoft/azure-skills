# BOM Migration — Gradle Programmatic Version Catalog (`settings.gradle`)

Some projects define version catalogs programmatically in `settings.gradle` / `settings.gradle.kts` instead of using a TOML file. OpenRewrite does not support this either ([openrewrite/rewrite#4852](https://github.com/openrewrite/rewrite/issues/4852)). Handle manually.

Use `TARGET_AZURE_SDK_BOM_VERSION` resolved in the workflow. Do not keep an existing programmatic catalog BOM version unless it exactly matches that value.

## Step 0 — Detect programmatic catalog usage

Look for a `dependencyResolutionManagement` block in `settings.gradle` or `settings.gradle.kts`:

```groovy
// settings.gradle (Groovy DSL)
dependencyResolutionManagement {
    versionCatalogs {
        libs {
            version("azureSdk", "1.41.4")
            version("azureStorage", "8.6.6")
            library("azure", "com.microsoft.azure", "azure").versionRef("azureSdk")
            library("azure-storage", "com.microsoft.azure", "azure-storage").versionRef("azureStorage")
        }
    }
}
```

```kotlin
// settings.gradle.kts (Kotlin DSL)
dependencyResolutionManagement {
    versionCatalogs {
        create("libs") {
            version("azureSdk", "1.41.4")
            version("azureStorage", "8.6.6")
            library("azure", "com.microsoft.azure", "azure").versionRef("azureSdk")
            library("azure-storage", "com.microsoft.azure", "azure-storage").versionRef("azureStorage")
        }
    }
}
```

The `library()` call can also use the two-arg `module` form (the same syntax applies to Kotlin DSL):
```groovy
library("azure", "com.microsoft.azure:azure").versionRef("azureSdk")
library("azure-inline", "com.microsoft.azure:azure").version("1.41.4")
```

If the project has this pattern and contains Azure dependency entries, use this section. The same `libs.<alias>` accessor syntax is used in `build.gradle` as with TOML catalogs.

## Step 1 — Add or upgrade the BOM

Add a version and library entry for the BOM inside the `versionCatalogs` block:

```groovy
// Groovy DSL
dependencyResolutionManagement {
    versionCatalogs {
        libs {
            version("azureSdkBom", "{bom_version}")
            library("azure-sdk-bom", "com.azure", "azure-sdk-bom").versionRef("azureSdkBom")
        }
    }
}
```

```kotlin
// Kotlin DSL
dependencyResolutionManagement {
    versionCatalogs {
        create("libs") {
            version("azureSdkBom", "{bom_version}")
            library("azure-sdk-bom", "com.azure", "azure-sdk-bom").versionRef("azureSdkBom")
        }
    }
}
```

If a BOM entry already exists, update the version string.

Add the platform dependency (if not already present).

Groovy DSL (`build.gradle`):
```groovy
dependencies {
    implementation enforcedPlatform(libs.azure.sdk.bom)
}
```

Kotlin DSL (`build.gradle.kts`):
```kotlin
dependencies {
    implementation(enforcedPlatform(libs.azure.sdk.bom))
}
```

## Step 2 — Remove explicit versions from BOM-managed Azure libraries

For each modern Azure library (`com.azure.*`) managed by the BOM, change its catalog entry to remove the version. Use the `withoutVersion()` call:

The snippets below show Groovy DSL (`settings.gradle`); the same code applies to Kotlin DSL (`settings.gradle.kts`).

Before:
```groovy
library("azure-identity", "com.azure", "azure-identity").versionRef("azureIdentity")
```

After:
```groovy
library("azure-identity", "com.azure", "azure-identity").withoutVersion()
```

For the two-arg module form (the same syntax applies to Kotlin DSL):
```groovy
// Before
library("azure-identity", "com.azure:azure-identity").versionRef("azureIdentity")
// After
library("azure-identity", "com.azure:azure-identity").withoutVersion()
```

Then remove any orphaned `version(...)` calls that are no longer referenced.

## Step 3 — Replace legacy Azure library entries with modern equivalents

For each legacy `com.microsoft.azure.*` library call:
1. Replace the group and artifact with the modern `com.azure.*` equivalent.
2. Change `.versionRef(...)` or `.version(...)` to `.withoutVersion()` if the new artifact is managed by the BOM.
3. Remove orphaned `version(...)` calls.
4. If you rename the alias (first argument), update **all** references in `build.gradle` / `build.gradle.kts` and any `bundle(...)` calls.

The snippets below show Groovy DSL (`settings.gradle`); the same code applies to Kotlin DSL (`settings.gradle.kts`).

Before:
```groovy
version("azureSdk", "1.41.4")
version("azureStorage", "8.6.6")
library("azure", "com.microsoft.azure", "azure").versionRef("azureSdk")
library("azure-storage", "com.microsoft.azure", "azure-storage").versionRef("azureStorage")
```

After:
```groovy
library("azure-resourcemanager", "com.azure.resourcemanager", "azure-resourcemanager").withoutVersion()
library("azure-storage-blob", "com.azure", "azure-storage-blob").withoutVersion()
```

Then update `build.gradle` (Groovy DSL):
```groovy
// Before
implementation libs.azure
implementation libs.azure.storage

// After
implementation libs.azure.resourcemanager
implementation libs.azure.storage.blob
```

Or `build.gradle.kts` (Kotlin DSL):
```kotlin
// Before
implementation(libs.azure)
implementation(libs.azure.storage)

// After
implementation(libs.azure.resourcemanager)
implementation(libs.azure.storage.blob)
```

## Step 4 — Handle bundles

If `bundle(...)` calls reference any renamed or removed aliases, update them:

Groovy DSL (`settings.gradle`):
```groovy
// Before
bundle("azureLibs", ["azure", "azure-storage"])
// After
bundle("azureLibs", ["azure-resourcemanager", "azure-storage-blob", "azure-identity"])
```

Kotlin DSL (`settings.gradle.kts`):
```kotlin
// Before
bundle("azureLibs", listOf("azure", "azure-storage"))
// After
bundle("azureLibs", listOf("azure-resourcemanager", "azure-storage-blob", "azure-identity"))
```

## Expected settings.gradle after migration

Groovy DSL (`settings.gradle`):
```groovy
dependencyResolutionManagement {
    versionCatalogs {
        libs {
            version("azureSdkBom", "{bom_version}")
            library("azure-sdk-bom", "com.azure", "azure-sdk-bom").versionRef("azureSdkBom")
            library("azure-identity", "com.azure", "azure-identity").withoutVersion()
            library("azure-resourcemanager", "com.azure.resourcemanager", "azure-resourcemanager").withoutVersion()
        }
    }
}
```

Kotlin DSL (`settings.gradle.kts`):
```kotlin
dependencyResolutionManagement {
    versionCatalogs {
        create("libs") {
            version("azureSdkBom", "{bom_version}")
            library("azure-sdk-bom", "com.azure", "azure-sdk-bom").versionRef("azureSdkBom")
            library("azure-identity", "com.azure", "azure-identity").withoutVersion()
            library("azure-resourcemanager", "com.azure.resourcemanager", "azure-resourcemanager").withoutVersion()
        }
    }
}
```
