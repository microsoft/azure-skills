# BOM Migration Guide

How to add or upgrade `azure-sdk-bom` and clean up redundant versions across all supported build configurations.

## Prerequisite — Python availability check

The Maven and plain-Gradle flows are automated by `scripts/upgrade_bom.py` (Python 3.10+). The script resolves the latest BOM internally; do not pass or pin a literal BOM version. Before picking a guide, verify Python is available:

The following check works in both **bash** and **PowerShell 7+** (the `||` operator is supported in both):

```bash
python3 --version || python --version
```

For Windows PowerShell 5.1, use:

```powershell
python3 --version; if ($LASTEXITCODE -ne 0) { python --version }
```

- **Python available** → use the script as documented in [bom-maven.md](./bom-maven.md) / [bom-gradle.md](./bom-gradle.md). If `upgrade_bom.py` fails for any reason, do not stop the migration; manually resolve the BOM version and follow the same guide's **Manual Fallback** section.
- **Python NOT available** → follow the **Manual Fallback** section in the same guide. Do not attempt to install Python; perform the edits by hand.

The TOML and programmatic-catalog guides ([bom-gradle-toml.md](./bom-gradle-toml.md), [bom-gradle-settings.md](./bom-gradle-settings.md)) are manual-only and unaffected by Python availability.

## Determine the latest BOM version

Resolve the target `azure-sdk-bom` version from the Azure SDK for Java source of truth before editing build files. This is mandatory: do not hardcode, guess, pin, or reuse an illustrative version from another example. Existing versions are accepted only when they exactly match the resolved latest stable version.
Always perform this resolution at the time the migration plan is generated. Never derive `TARGET_AZURE_SDK_BOM_VERSION` from the application being migrated, from a previously generated plan, from package-specific examples, or from model memory. If a resolved version differs from an existing `azure-sdk-bom` in the project, the existing BOM is stale and must be upgraded.

The following invocation works identically in **bash** and **PowerShell** (no shell-specific syntax):

```bash
# Path is relative to the skill directory (plugin/skills/azure-upgrade/)
python3 ./references/languages/java/scripts/upgrade_bom.py --get-latest-version
# or: python ./references/languages/java/scripts/upgrade_bom.py --get-latest-version
```

If Python is not available or the `--get-latest-version` command fails, fetch `https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/boms/azure-sdk-bom/pom.xml` directly and use the `<version>` value declared in that BOM `pom.xml`.

Do not continue until you have resolved that latest stable version explicitly. Add only that value to the plan's `Guidelines` section as `TARGET_AZURE_SDK_BOM_VERSION = <resolved-version>`.

## Decision Tree

```
Is the project Maven?
├─ YES → Maven projects (bom-maven.md)
└─ NO (Gradle)
     ├─ Does gradle/libs.versions.toml exist with Azure entries?
     │    └─ YES → TOML catalog steps (bom-gradle-toml.md)
     ├─ Does settings.gradle define a programmatic versionCatalogs block with Azure entries?
     │    └─ YES → Programmatic catalog steps (bom-gradle-settings.md)
     └─ Neither (plain build.gradle dependencies)
          └─ Plain Gradle projects (bom-gradle.md)
```

> 💡 **Tip:** To check which artifacts are managed by the BOM, fetch
> `https://repo1.maven.org/maven2/com/azure/azure-sdk-bom/{bom_version}/azure-sdk-bom-{bom_version}.pom`
> and look for `<dependency>` entries.

## Build-System Guides

| Build system                  | Guide                                              |
| ----------------------------- | -------------------------------------------------- |
| Maven                         | [bom-maven.md](./bom-maven.md)                     |
| Gradle (no version catalog)   | [bom-gradle.md](./bom-gradle.md)                   |
| Gradle + TOML version catalog | [bom-gradle-toml.md](./bom-gradle-toml.md)         |
| Gradle + programmatic catalog | [bom-gradle-settings.md](./bom-gradle-settings.md) |

## Validation

See the [Validation Checklist](./bom-validation.md) — covers all build systems including TOML and programmatic `settings.gradle` catalogs.
