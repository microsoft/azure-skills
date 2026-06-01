# Azure SDK Migration Guidelines

## Context

The application is identified using legacy Azure SDKs for Java (`com.microsoft.azure.*`). These libraries reached end of support in 2023. They are not recommended for use in production, should be migrated to the latest Azure SDKs with the latest security patches and new capabilities support.

Follow these steps:

- **Inventory legacy dependencies**: Use tools such as `mvn dependency:tree` or `gradlew dependencies` to find every `com.microsoft.azure.*` SDK and map each one to its modern counterpart under `com.azure.*`. Do **not** rely solely on the root reactor — also grep the entire repository for legacy coordinates so you catch build files that aren't reachable from the root project. Run from the repo root:

  ```bash
  # Find every file referencing legacy groupIds/artifacts, including CI, samples, parent poms, buildSrc, version catalogs, Dockerfiles, and docs.
  grep -RIn --exclude-dir={.git,target,build,node_modules,out} \
    -E 'com\.microsoft\.azure(\.|:)|microsoft-azure-|azure-eventhubs-eph|azure-keyvault(:|["'\''])' .
  ```

  PowerShell equivalent (run from repo root):

  ```powershell
  Get-ChildItem -Path . -Recurse -File |
    Where-Object { $_.FullName -notmatch '(\\|/)(\.git|target|build|node_modules|out)(\\|/)' } |
    Select-String -Pattern 'com\.microsoft\.azure(\.|:)|microsoft-azure-|azure-eventhubs-eph|azure-keyvault(:|["''])'
  ```

  Commonly overlooked locations:`.ci/**/pom.xml`, `ci/**`, parent/BOM poms, `buildSrc/`, `gradle/libs.versions.toml`, `settings.gradle(.kts)`, `archetype-resources/`, sample sub-modules, Dockerfiles, shell/PowerShell scripts, and README snippets. Every hit must end up on the migration file list.

- **Adopt supported SDKs**: Replace the legacy dependencies with their modern equivalents in your `pom.xml` or `build.gradle`, following the migration guide to align feature parity and new SDK names.

- **Update application code**: Refactor your code to the builder-based APIs, updated authentication flows (Azure Identity), and modern async or reactive patterns required by the latest SDKs. Add concise comments explaining non-obvious changes.

- **Test thoroughly**: Run unit, integration, and end-to-end tests to validate that the modern SDKs behave as expected, focusing on authentication, retry, and serialization differences.

## Migration Guide

### Assumption

- Project is Maven or Gradle.
- Java code is on JDK 8 or above.

### Migrate dependencies (Add them to plan guidelines when generating plan)

Immediately load and read [BOM Migration Guide](./bom-migration/bom-migration.md) before choosing `TARGET_AZURE_SDK_BOM_VERSION`; do not rely on this summary alone. The guide covers how to determine the latest BOM version, plus Maven, plain Gradle, TOML version catalogs (`libs.versions.toml`), and programmatic version catalogs (`settings.gradle`).

When writing the plan's `Guidelines` section, use only the latest stable `azure-sdk-bom` resolved by the BOM guide; do **not** infer it from the project, reuse an existing BOM version, copy a value from examples, or trust model memory. Record it as `TARGET_AZURE_SDK_BOM_VERSION = <resolved-version>` and use that exact value throughout the migration.

### Migrate Java Code

- Make a list of source code/maven/gradle files that contains legacy SDK packages. Migrate each of them.
- Determine legacy SDK artifacts according to previous files, find suitable migration guides in [Package-Specific Migration Guides](#package-specific-migration-guides) and follow the guides whenever possible. Record which migration guide URL you used for each legacy package (e.g., in your plan or commit messages), so you can validate against them later.
- **Do not change the Java `package ...;` declaration at the top of each source file, and do not rename or move the source file's directory path to match a new SDK package structure.** Keep every `.java` file in its original directory; only update `import` statements and type usages inside the file body. For example, if a file lives in `src/main/java/com/microsoft/azure/eventprocessorhosts/Consumer.java` with `package com.microsoft.azure.eventprocessorhosts;`, it must stay in that exact directory and keep that exact package declaration — even though the modern SDK uses `com.azure.messaging.eventhubs`.
- Do not upgrade JDK version, if it is already JDK 8 or above.
- If there is test in the project, Java code there also need to be updated.

## Package-Specific Source Code Guidelines (Add them to plan guidelines when generating plan)

Use these package-specific references:

- [com.microsoft.azure.management.\*\*](./package-specific/com.microsoft.azure.management.md)
- [com.microsoft.azure.eventprocessorhost](./package-specific/com.microsoft.azure.eventprocessorhost.md)

## Validation

**Make sure**
- Migrated project pass compilation.
- All tests pass. Don't silently skip tests.
- The plan's `Guidelines` section records the freshly resolved latest stable BOM target exactly as `TARGET_AZURE_SDK_BOM_VERSION = <resolved-version>`; this value must not remain a placeholder, must not be copied from the original project, and must match the current Azure SDK for Java BOM source of truth at validation time.
- No legacy SDK dependencies/references exist. This is a **hard gate**, not a self-assessment — you must prove it by running the commands below from the repo root and showing they return zero hits. Do not declare migration complete until all three return empty:

  ```bash
  # 1. Legacy groupId / artifact references in ANY text file (pom.xml, *.gradle, *.gradle.kts, libs.versions.toml, Dockerfile, *.sh, *.md, etc.)
  grep -RIn --exclude-dir={.git,target,build,node_modules,out} \
    -E 'com\.microsoft\.azure(\.|:)|microsoft-azure-|azure-eventhubs-eph|azure-keyvault(:|["'\''])' .

  # 2. Legacy imports still in Java sources
  grep -RIn --include='*.java' -E '^\s*import\s+com\.microsoft\.azure\.' .

  # 3. Every pom.xml and *.gradle(.kts) file in the repo (not just the root reactor) — eyeball each for legacy coordinates
  find . -type d \( -name .git -o -name target -o -name build -o -name node_modules \) -prune -o \
    -type f \( -name 'pom.xml' -o -name '*.gradle' -o -name '*.gradle.kts' -o -name 'libs.versions.toml' \) -print
  ```

  PowerShell equivalent (run from repo root):

  ```powershell
  # 1. Legacy groupId / artifact references in ANY text file
  Get-ChildItem -Path . -Recurse -File |
    Where-Object { $_.FullName -notmatch '(\\|/)(\.git|target|build|node_modules|out)(\\|/)' } |
    Select-String -Pattern 'com\.microsoft\.azure(\.|:)|microsoft-azure-|azure-eventhubs-eph|azure-keyvault(:|["''])'

  # 2. Legacy imports still in Java sources
  Get-ChildItem -Path . -Recurse -File -Filter *.java |
    Where-Object { $_.FullName -notmatch '(\\|/)(\.git|target|build|node_modules|out)(\\|/)' } |
    Select-String -Pattern '^\s*import\s+com\.microsoft\.azure\.'

  # 3. Every pom.xml and *.gradle(.kts) file in the repo — eyeball each for legacy coordinates
  Get-ChildItem -Path . -Recurse -File -Include 'pom.xml','*.gradle','*.gradle.kts','libs.versions.toml' |
    Where-Object { $_.FullName -notmatch '(\\|/)(\.git|target|build|node_modules)(\\|/)' } |
    Select-Object -ExpandProperty FullName
  ```

  Pay special attention to files outside the root Maven/Gradle reactor— e.g. `.ci/**/pom.xml`, `ci/**`, `buildSrc/`, sample sub-modules, archetype resources — these are frequently missed because `mvn dependency:tree` on the root project never visits them.
- If azure-sdk-bom is used, ensure the BOM version exactly matches the resolved latest stable version recorded in the plan's `Guidelines` section as `TARGET_AZURE_SDK_BOM_VERSION` and there are **NO** explicit version dependencies for Azure libraries that are in azure-sdk-bom.
  E.g. Instead of `implementation 'com.azure.resourcemanager:azure-resourcemanager:2.60.0'`, we should use `implementation 'com.azure.resourcemanager:azure-resourcemanager'`.
  For Azure libraries in azure-sdk-bom, check https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/boms/azure-sdk-bom/pom.xml.
  If the BOM version is missing, or differs from the resolved latest stable version, or individual Azure packages still have explicit versions that should be managed by the BOM, follow the appropriate section in [BOM Migration Guide](./bom-migration/bom-migration.md) to fix it.
- **Version catalog projects**: Follow the [BOM Validation Checklist](./bom-migration/bom-validation.md) — it covers TOML, programmatic `settings.gradle` catalogs, and plain Gradle.
- For each migration guide you recorded during migration:
  1. Fetch and read the full content of the guide URL.
  2. Identify the migrated source files that correspond to that guide's package.
  3. Verify the migrated code follows the guide's recommended API replacements, class mappings, authentication patterns, and async/sync conventions.
  4. Fix any deviations — do not just report them.

## Package-Specific Migration Guides

- [Migrate to `com.azure.resourcemanager.**` from `com.microsoft.azure.management.**`](https://aka.ms/java-track2-migration-guide)
- [Migrate to com.azure:azure-messaging-servicebus from com.microsoft.azure:azure-servicebus](https://aka.ms/azsdk/java/migrate/sb)
- [Migrate to azure-messaging-eventhubs from azure-eventhubs and azure-eventhubs-eph](https://aka.ms/azsdk/java/migrate/eh)
- [Migrate to `azure-messaging-eventgrid` from `microsoft-azure-eventgrid`](https://aka.ms/azsdk/java/migrate/eg)
- [Storage Blob Service SDK Migration Guide from 8.x to 12.x](https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/storage/azure-storage-blob/migrationGuides/V8_V12.md)
- [Storage Blob Service SDK Migration Guide from 10.x/11.x to 12.x](https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/storage/azure-storage-blob/migrationGuides/V10_V12.md)
- [Storage Queue Service SDK Migration Guide from 8.x to 12.x](https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/storage/azure-storage-queue/migrationGuides/V8_V12.md)
- [Storage File Share Service SDK Migration Guide from 8.x to 12.x](https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/storage/azure-storage-file-share/migrationGuides/V8_V12.md)
- [Migrate to azure-security-keyvault-secrets from azure-keyvault](https://aka.ms/azsdk/java/migrate/kv-secrets)
- [Migrate to azure-security-keyvault-keys from azure-keyvault](https://aka.ms/azsdk/java/migrate/kv-keys)
- [Migrate to azure-security-keyvault-certificates from azure-keyvault](https://aka.ms/azsdk/java/migrate/kv-cert)
- [Migrate to `Azure-Compute-Batch` from `Microsoft-Azure-Batch`](https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/batch/azure-compute-batch/MigrationGuide.md)
- [Migrate to `azure-ai-documentintelligence` from `azure-ai-formrecognizer`](https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/documentintelligence/azure-ai-documentintelligence/MIGRATION_GUIDE.md)
- [Migrate to `azure-ai-formrecognizer 4.0.0-beta.1 - above` from `azure-ai-formrecognizer 3.1.x - lower`](https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/formrecognizer/azure-ai-formrecognizer/migration-guide.md)
- [Migration Guide from Azure OpenAI Java SDK to OpenAI Java SDK](https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/openai/azure-ai-openai-stainless/MIGRATION.md)
- [Migrate to azure-monitor-query from azure-loganalytics and azure-applicationinsights-query](https://aka.ms/azsdk/java/migrate/monitorquery)
