# BOM Migration — Gradle Projects (No Version Catalogs)

> **Python/script availability**: The script below requires Python 3.10+. If `python3 --version` (or `python --version`) fails, or if `upgrade_bom.py` exits unsuccessfully, skip the script path and follow [Manual Fallback](#manual-fallback-no-python-or-script-failure) instead.

## Automated (Python available)

Run the `upgrade_bom.py` script located at `references/languages/java/scripts/upgrade_bom.py` (relative to this skill). It resolves the latest stable BOM version, auto-detects Gradle, and performs:

1. **Set/upgrade the BOM** — adds `enforcedPlatform("com.azure:azure-sdk-bom:...")` if missing, or upgrades the version.
2. **Remove redundant explicit versions** — strips inline version strings from Azure dependencies managed by the BOM.

The following invocation works identically in **bash** and **PowerShell**:

```bash
# Path is relative to the skill directory (plugin/skills/azure-upgrade/)
python3 ./references/languages/java/scripts/upgrade_bom.py <project_dir>
```

Options:
- `--gradle <cmd>` — override the Gradle command (default: auto-detects `gradlew` or `gradle`).

If the script fails after starting, treat that as an automation failure only: keep the resolved `TARGET_AZURE_SDK_BOM_VERSION`, manually apply the fallback steps below, and continue validation.

Under the hood (OpenRewrite recipes):
- **Add BOM**: `AddPlatformDependency` ([docs](https://docs.openrewrite.org/recipes/gradle/addplatformdependency))
- **Upgrade BOM**: `UpgradeDependencyVersion` ([docs](https://docs.openrewrite.org/recipes/gradle/upgradedependencyversion))
- **Remove redundant versions**: `RemoveRedundantDependencyVersions` ([docs](https://docs.openrewrite.org/recipes/gradle/removeredundantdependencyversions))

> ⚠️ **Warning:** The script does **not** support Gradle version catalogs — neither TOML files nor programmatic `settings.gradle` catalogs. If the project uses either, follow [TOML catalog steps](./bom-gradle-toml.md) or [programmatic catalog steps](./bom-gradle-settings.md) instead.

## Expected build.gradle after migration

Groovy DSL (`build.gradle`):
```groovy
dependencies {
    implementation enforcedPlatform("com.azure:azure-sdk-bom:{bom_version}")

    implementation "com.azure:azure-identity"
    implementation "com.azure.resourcemanager:azure-resourcemanager"
}
```

Kotlin DSL (`build.gradle.kts`):
```kotlin
dependencies {
    implementation(enforcedPlatform("com.azure:azure-sdk-bom:{bom_version}"))

    implementation("com.azure:azure-identity")
    implementation("com.azure.resourcemanager:azure-resourcemanager")
}
```

## Manual Fallback (no Python or script failure)

When Python is unavailable or `upgrade_bom.py` fails, edit `build.gradle` (or `build.gradle.kts`) directly. Apply the same two steps as the script.

### Step 1 — Add or upgrade the BOM platform

Inside the `dependencies { }` block, add or update the `enforcedPlatform` line for `azure-sdk-bom`:

Groovy DSL:
```groovy
dependencies {
    implementation enforcedPlatform("com.azure:azure-sdk-bom:{bom_version}")
    // ...other dependencies...
}
```

Kotlin DSL:
```kotlin
dependencies {
    implementation(enforcedPlatform("com.azure:azure-sdk-bom:{bom_version}"))
    // ...other dependencies...
}
```

- **If the line exists**: update only the version to `{bom_version}`.
- **If the line is missing**: insert it at the top of the `dependencies` block.
- Use the same configuration (`implementation`, `api`, `compileOnly`, etc.) the project already uses for Azure deps. Repeat the platform line per configuration if needed.
- **Multi-project build**: add the platform line in every subproject that declares Azure dependencies, or apply it once via a shared `subprojects { }` / convention plugin.

### Step 2 — Remove redundant explicit versions

For every Azure dependency whose group starts with `com.azure` and is managed by the BOM (verify against `https://repo1.maven.org/maven2/com/azure/azure-sdk-bom/{bom_version}/azure-sdk-bom-{bom_version}.pom`), strip the version coordinate.

Groovy DSL — string notation:
```groovy
// Before
implementation "com.azure:azure-identity:1.13.0"
// After
implementation "com.azure:azure-identity"
```

Groovy DSL — map notation:
```groovy
// Before
implementation group: "com.azure", name: "azure-identity", version: "1.13.0"
// After
implementation group: "com.azure", name: "azure-identity"
```

Kotlin DSL:
```kotlin
// Before
implementation("com.azure:azure-identity:1.13.0")
// After
implementation("com.azure:azure-identity")
```

Do **not** strip versions from artifacts that are not managed by the BOM.

### Step 3 — Verify

Run the Gradle wrapper to inspect the resolved classpath. Use the form appropriate for your shell:

```bash
# bash / macOS / Linux
./gradlew dependencies --configuration runtimeClasspath
```

```powershell
# PowerShell on Windows
.\gradlew.bat dependencies --configuration runtimeClasspath
```

Then confirm:
- The platform `com.azure:azure-sdk-bom:{bom_version}` appears.
- `{bom_version}` equals `TARGET_AZURE_SDK_BOM_VERSION`.
- All BOM-managed Azure artifacts resolve to versions sourced from the BOM.

Then continue with the validation checklist in [bom-validation.md](./bom-validation.md).
