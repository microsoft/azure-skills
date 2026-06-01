# BOM Migration — Maven Projects

> **Python/script availability**: The script below requires Python 3.10+. If `python3 --version` (or `python --version`) fails, or if `upgrade_bom.py` exits unsuccessfully, skip the script path and follow [Manual Fallback](#manual-fallback-no-python-or-script-failure) instead.

## Automated (Python available)

Run the `upgrade_bom.py` script located at `references/languages/java/scripts/upgrade_bom.py` (relative to this skill). It resolves the latest stable BOM version, auto-detects Maven, and performs two steps:

1. **Set/upgrade the BOM** — adds `azure-sdk-bom` if missing, or upgrades the version if already present.
2. **Remove redundant explicit versions** — strips explicit `<version>` tags from individual Azure dependencies that are now managed by the BOM.

The following invocation works identically in **bash** and **PowerShell**:

```bash
# Path is relative to the skill directory (plugin/skills/azure-upgrade/)
python3 ./references/languages/java/scripts/upgrade_bom.py <project_dir>
```

Options:
- `--mvn <cmd>` — override the Maven command (default: auto-detects `mvnw` or `mvn`).

If the script fails after starting, treat that as an automation failure only: keep the resolved `TARGET_AZURE_SDK_BOM_VERSION`, manually apply the fallback steps below, and continue validation.

Under the hood (OpenRewrite recipes):
- **Add BOM**: `AddManagedDependency` ([docs](https://docs.openrewrite.org/recipes/maven/addmanageddependency))
- **Upgrade BOM**: `UpgradeDependencyVersion` ([docs](https://docs.openrewrite.org/recipes/maven/upgradedependencyversion))
- **Remove redundant versions**: `RemoveRedundantDependencyVersions` ([docs](https://docs.openrewrite.org/recipes/maven/removeredundantdependencyversions))

## Expected pom.xml after migration

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>com.azure</groupId>
            <artifactId>azure-sdk-bom</artifactId>
            <version>{bom_version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>

<dependencies>
    <dependency>
        <groupId>com.azure</groupId>
        <artifactId>azure-identity</artifactId>
    </dependency>
    <dependency>
        <groupId>com.azure.resourcemanager</groupId>
        <artifactId>azure-resourcemanager</artifactId>
    </dependency>
</dependencies>
```

## Manual Fallback (no Python or script failure)

When Python is unavailable or `upgrade_bom.py` fails, edit `pom.xml` directly. Apply the same two steps as the script:

### Step 1 — Add or upgrade `azure-sdk-bom`

Locate the `<dependencyManagement><dependencies>` block (create it inside `<project>` if absent). Add or update the BOM entry:

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>com.azure</groupId>
            <artifactId>azure-sdk-bom</artifactId>
            <version>{bom_version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
        <!-- keep any other managed dependencies here -->
    </dependencies>
</dependencyManagement>
```

- **If the entry exists**: update only the `<version>` value to `{bom_version}`.
- **If the entry is missing**: insert the full `<dependency>` block above. Preserve any other existing managed dependencies.
- **Multi-module project**: add the BOM in the parent (aggregator) `pom.xml` only. Child modules inherit it.

### Step 2 — Remove redundant explicit versions

For every `<dependency>` whose `<groupId>` starts with `com.azure` (e.g. `com.azure`, `com.azure.resourcemanager`, `com.azure.spring`), check whether the BOM manages it (see the BOM POM at `https://repo1.maven.org/maven2/com/azure/azure-sdk-bom/{bom_version}/azure-sdk-bom-{bom_version}.pom`). If managed:

- Remove the `<version>` element entirely.
- Leave `<groupId>`, `<artifactId>`, `<scope>`, `<classifier>`, `<exclusions>`, etc. unchanged.

Before:
```xml
<dependency>
    <groupId>com.azure</groupId>
    <artifactId>azure-identity</artifactId>
    <version>1.13.0</version>
</dependency>
```

After:
```xml
<dependency>
    <groupId>com.azure</groupId>
    <artifactId>azure-identity</artifactId>
</dependency>
```

Do **not** strip versions from artifacts not managed by the BOM (verify each one against the BOM POM).

### Step 3 — Verify

Run `mvn -q -DskipTests dependency:tree` (the same command works in both **bash** and **PowerShell**) and confirm:
- `com.azure:azure-sdk-bom:pom:{bom_version}:import` appears in the managed dependencies and `{bom_version}` equals `TARGET_AZURE_SDK_BOM_VERSION`.
- All BOM-managed Azure artifacts resolve to versions from `{bom_version}`.

Then continue with the validation checklist in [bom-validation.md](./bom-validation.md).
