#!/usr/bin/env python3
"""Upgrade or add azure-sdk-bom in a Maven or Gradle project using OpenRewrite.

Detects the build system automatically and applies the appropriate OpenRewrite
recipes.  All operations use OpenRewrite — no manual XML/text manipulation.

Step 1 – Add or upgrade BOM:
- Maven (add):     org.openrewrite.maven.AddManagedDependency
- Maven (upgrade): org.openrewrite.maven.UpgradeDependencyVersion
- Gradle (add):    org.openrewrite.gradle.AddPlatformDependency
- Gradle (upgrade):org.openrewrite.gradle.UpgradeDependencyVersion

Step 2 – Remove redundant explicit versions:
- Maven:  org.openrewrite.maven.RemoveRedundantDependencyVersions
- Gradle: org.openrewrite.gradle.RemoveRedundantDependencyVersions

Usage:
    python3 upgrade_bom.py <project_dir> [latest] [options]
    python3 upgrade_bom.py --get-latest-version

Arguments:
    project_dir   Path to the project root (must contain pom.xml or build.gradle).
    latest        Optional compatibility token. Explicit version pins are rejected.

Options:
    --mvn <cmd>     Maven command override.
    --gradle <cmd>  Gradle command override.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

GROUP_ID = "com.azure"
ARTIFACT_ID = "azure-sdk-bom"
BOM_POM_URL = "https://raw.githubusercontent.com/Azure/azure-sdk-for-java/main/sdk/boms/azure-sdk-bom/pom.xml"
POM_NAMESPACE = {"m": "http://maven.apache.org/POM/4.0.0"}
MIN_BOM_VERSION = "1.3.0"
LATEST_VERSION_SENTINEL = "latest"
HTTP_TIMEOUT_SECONDS = 30
STABLE_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# Maven constants
MVN_REWRITE_PLUGIN = "org.openrewrite.maven:rewrite-maven-plugin"
MVN_REWRITE_ARTIFACT_COORDS = "org.openrewrite:rewrite-maven"
MVN_UPGRADE_RECIPE = "org.openrewrite.maven.UpgradeDependencyVersion"
MVN_ADD_MANAGED_RECIPE = "org.openrewrite.maven.AddManagedDependency"
MVN_REMOVE_REDUNDANT_RECIPE = "org.openrewrite.maven.RemoveRedundantDependencyVersions"

# Gradle constants
GRADLE_UPGRADE_RECIPE = "org.openrewrite.gradle.UpgradeDependencyVersion"
GRADLE_ADD_PLATFORM_RECIPE = "org.openrewrite.gradle.AddPlatformDependency"
GRADLE_REMOVE_REDUNDANT_RECIPE = "org.openrewrite.gradle.RemoveRedundantDependencyVersions"
REWRITE_YML_NAME = "rewrite.yml"
GRADLE_PLUGIN_MARKER = "// --- openrewrite-upgrade-bom-plugin (auto-added, safe to remove) ---"

# ---------------------------------------------------------------------------
# Build-system detection
# ---------------------------------------------------------------------------

def _detect_build_system(project_dir: str) -> str:
    """Return 'maven' or 'gradle' depending on which build file is present."""
    if os.path.isfile(os.path.join(project_dir, "pom.xml")):
        return "maven"
    for name in ("build.gradle", "build.gradle.kts"):
        if os.path.isfile(os.path.join(project_dir, name)):
            return "gradle"
    return "unknown"


def _get_latest_bom_version() -> str:
    try:
        with urllib.request.urlopen(BOM_POM_URL, timeout=HTTP_TIMEOUT_SECONDS) as response:
            pom_xml = response.read()
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to download {BOM_POM_URL}: {exc}") from exc

    try:
        root = ET.fromstring(pom_xml)
    except ET.ParseError as exc:
        raise SystemExit(f"Failed to parse BOM pom.xml: {exc}") from exc

    version = root.findtext("m:version", namespaces=POM_NAMESPACE)
    if not version:
        raise SystemExit("Failed to find the azure-sdk-bom <version> in pom.xml")

    return version.strip()


def _parse_stable_semver(version: str) -> tuple[int, int, int]:
    match = STABLE_SEMVER_RE.fullmatch(version.strip())
    if not match:
        raise ValueError(
            f"Invalid azure-sdk-bom version '{version}'. Expected stable MAJOR.MINOR.PATCH."
        )
    return tuple(int(part) for part in match.groups())


def _validate_minimum_bom_version(version: str) -> None:
    parsed = _parse_stable_semver(version)
    minimum = _parse_stable_semver(MIN_BOM_VERSION)
    if parsed < minimum:
        raise ValueError(
            f"azure-sdk-bom {version} is below the minimum supported version "
            f"{MIN_BOM_VERSION}; resolve the latest stable version from {BOM_POM_URL}."
        )


def _resolve_latest_bom_version(requested_version: str | None) -> str:
    if requested_version and requested_version.strip().lower() != LATEST_VERSION_SENTINEL:
        raise ValueError(
            "Explicit azure-sdk-bom version pins are not allowed in this migration flow. "
            f"Use no version argument, or use '{LATEST_VERSION_SENTINEL}' for compatibility."
        )

    latest = _get_latest_bom_version()
    _validate_minimum_bom_version(latest)
    print(f"[upgrade_bom] Resolved latest azure-sdk-bom version: {latest}")
    print(f"[upgrade_bom] Source: {BOM_POM_URL}")
    return latest


# ---------------------------------------------------------------------------
# Maven helpers
# ---------------------------------------------------------------------------

def _detect_maven(project_dir: str) -> str:
    if sys.platform == "win32":
        wrapper = os.path.join(project_dir, "mvnw.cmd")
        # .cmd files on Windows are invoked by the shell; no executable bit needed.
        if os.path.isfile(wrapper):
            return wrapper
    else:
        wrapper = os.path.join(project_dir, "mvnw")
        if os.path.isfile(wrapper):
            if not os.access(wrapper, os.X_OK):
                # Wrapper exists but isn't executable (common after fresh clones
                # on filesystems that don't preserve the +x bit). Try to fix it.
                try:
                    mode = os.stat(wrapper).st_mode
                    os.chmod(wrapper, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    print(f"[upgrade_bom] Added executable bit to {wrapper}.")
                except OSError as exc:
                    print(
                        f"[upgrade_bom] WARNING: mvnw exists at {wrapper} but is not "
                        f"executable and chmod failed ({exc}); falling back to 'mvn'.",
                        file=sys.stderr,
                    )
                    return "mvn"
            if os.access(wrapper, os.X_OK):
                return wrapper
    return "mvn"


def _has_maven_bom_entry(pom_path: str) -> bool:
    try:
        tree = ET.parse(pom_path)
    except ET.ParseError:
        return False
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
    for dep in tree.findall(".//m:dependencyManagement/m:dependencies/m:dependency", ns):
        gid = dep.find("m:groupId", ns)
        aid = dep.find("m:artifactId", ns)
        if gid is not None and aid is not None:
            if gid.text == GROUP_ID and aid.text == ARTIFACT_ID:
                return True
    for dep in tree.findall(".//dependencyManagement/dependencies/dependency"):
        gid = dep.find("groupId")
        aid = dep.find("artifactId")
        if gid is not None and aid is not None:
            if gid.text == GROUP_ID and aid.text == ARTIFACT_ID:
                return True
    return False


def _run_maven_recipe(mvn_cmd: str, project_dir: str, recipe: str, options: str) -> int:
    """Run an OpenRewrite recipe via the rewrite-maven-plugin."""
    cmd = [
        mvn_cmd, "-U",
        f"{MVN_REWRITE_PLUGIN}:run",
        f"-Drewrite.recipeArtifactCoordinates={MVN_REWRITE_ARTIFACT_COORDS}",
        f"-Drewrite.activeRecipes={recipe}",
        f"-Drewrite.options={options}",
    ]
    print(f"[upgrade_bom] Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=project_dir).returncode


def _handle_maven(project_dir: str, bom_version: str, mvn_cmd: str | None) -> int:
    pom_path = os.path.join(project_dir, "pom.xml")
    mvn = mvn_cmd or _detect_maven(project_dir)

    # Step 1: Add or upgrade the BOM
    if not _has_maven_bom_entry(pom_path):
        print("[upgrade_bom] No existing azure-sdk-bom entry found — adding via AddManagedDependency.")
        options = ",".join([
            f"groupId={GROUP_ID}",
            f"artifactId={ARTIFACT_ID}",
            f"version={bom_version}",
            "type=pom",
            "scope=import",
        ])
        rc = _run_maven_recipe(mvn, project_dir, MVN_ADD_MANAGED_RECIPE, options)
        if rc != 0:
            print(f"[upgrade_bom] ERROR: AddManagedDependency exited with code {rc}", file=sys.stderr)
            return rc
        print(f"[upgrade_bom] azure-sdk-bom {bom_version} added successfully.")
    else:
        print(f"[upgrade_bom] Existing azure-sdk-bom entry found — upgrading to {bom_version}.")
        options = ",".join([
            f"groupId={GROUP_ID}",
            f"artifactId={ARTIFACT_ID}",
            f"newVersion={bom_version}",
            "overrideManagedVersion=true",
        ])
        rc = _run_maven_recipe(mvn, project_dir, MVN_UPGRADE_RECIPE, options)
        if rc != 0:
            print(f"[upgrade_bom] ERROR: UpgradeDependencyVersion exited with code {rc}", file=sys.stderr)
            return rc
        print(f"[upgrade_bom] azure-sdk-bom upgraded to {bom_version} successfully.")

    # Step 2: Remove explicit versions from Azure deps managed by the BOM
    print("[upgrade_bom] Removing redundant explicit versions for Azure dependencies...")
    options = f"groupPattern={GROUP_ID}*,onlyIfManagedVersionIs=GTE"
    rc = _run_maven_recipe(mvn, project_dir, MVN_REMOVE_REDUNDANT_RECIPE, options)
    if rc != 0:
        print(f"[upgrade_bom] WARNING: RemoveRedundantDependencyVersions exited with code {rc}", file=sys.stderr)
    else:
        print("[upgrade_bom] Redundant explicit versions removed successfully.")
    return rc


# ---------------------------------------------------------------------------
# Gradle helpers
# ---------------------------------------------------------------------------

def _detect_gradle(project_dir: str) -> str:
    if sys.platform == "win32":
        wrapper = os.path.join(project_dir, "gradlew.bat")
        if os.path.isfile(wrapper):
            return wrapper
    else:
        wrapper = os.path.join(project_dir, "gradlew")
        if os.path.isfile(wrapper):
            if not os.access(wrapper, os.X_OK):
                try:
                    mode = os.stat(wrapper).st_mode
                    os.chmod(wrapper, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    print(f"[upgrade_bom] Added executable bit to {wrapper}.")
                except OSError as exc:
                    print(
                        f"[upgrade_bom] WARNING: gradlew exists at {wrapper} but is not "
                        f"executable and chmod failed ({exc}); falling back to 'gradle'.",
                        file=sys.stderr,
                    )
                    return "gradle"
            if os.access(wrapper, os.X_OK):
                return wrapper
    return "gradle"


def _find_gradle_build_file(project_dir: str) -> str | None:
    for name in ("build.gradle", "build.gradle.kts"):
        path = os.path.join(project_dir, name)
        if os.path.isfile(path):
            return path
    return None


def _is_kotlin_dsl(build_file: str) -> bool:
    return build_file.endswith(".kts")


def _has_gradle_bom_entry(build_file: str) -> bool:
    """Check whether build.gradle already references azure-sdk-bom."""
    try:
        with open(build_file, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return False
    return f"{GROUP_ID}:{ARTIFACT_ID}" in content


def _create_rewrite_yml(project_dir: str, bom_version: str, has_bom: bool) -> str:
    """Create a temporary rewrite.yml with the appropriate OpenRewrite recipes.

    When has_bom is True, uses UpgradeDependencyVersion to upgrade the existing BOM.
    When has_bom is False, uses AddPlatformDependency to add a new enforcedPlatform BOM.
    Always includes RemoveRedundantDependencyVersions as a final step.
    """
    yml_path = os.path.join(project_dir, REWRITE_YML_NAME)
    recipes: list[str] = []

    if has_bom:
        recipes.append(textwrap.dedent(f"""\
          - org.openrewrite.gradle.UpgradeDependencyVersion:
              groupId: {GROUP_ID}
              artifactId: {ARTIFACT_ID}
              newVersion: {bom_version}"""))
    else:
        recipes.append(textwrap.dedent(f"""\
          - org.openrewrite.gradle.AddPlatformDependency:
              groupId: {GROUP_ID}
              artifactId: {ARTIFACT_ID}
              version: {bom_version}
              configuration: implementation
              enforced: true"""))

    recipes.append(textwrap.dedent(f"""\
          - org.openrewrite.gradle.RemoveRedundantDependencyVersions:
              groupPattern: {GROUP_ID}*
              onlyIfManagedVersionIs: GTE"""))

    yml_content = textwrap.dedent("""\
        ---
        type: specs.openrewrite.org/v1beta/recipe
        name: com.azure.UpgradeBom
        displayName: Upgrade azure-sdk-bom and remove redundant versions
        recipeList:
    """) + "\n".join(recipes) + "\n"

    with open(yml_path, "w", encoding="utf-8") as f:
        f.write(yml_content)
    print(f"[upgrade_bom] Created {yml_path}")
    return yml_path


def _inject_gradle_rewrite_plugin(build_file: str) -> bool:
    """Temporarily add the OpenRewrite plugin to build.gradle if not present.

    Returns True if the plugin block was injected (and should be cleaned up).
    """
    with open(build_file, "r", encoding="utf-8") as f:
        content = f.read()

    if "org.openrewrite.rewrite" in content:
        return False

    kotlin = _is_kotlin_dsl(build_file)
    if kotlin:
        plugin_line = '    id("org.openrewrite.rewrite") version "latest.release"'
    else:
        plugin_line = '    id "org.openrewrite.rewrite" version "latest.release"'

    rewrite_block_kt = textwrap.dedent("""\

        rewrite {
            activeRecipe("com.azure.UpgradeBom")
        }

        repositories {
            mavenCentral()
        }
    """)
    rewrite_block_groovy = rewrite_block_kt  # same syntax for both DSLs here

    plugins_pattern = re.compile(r"(plugins\s*\{)", re.MULTILINE)
    match = plugins_pattern.search(content)
    if match:
        insert_pos = match.end()
        # content[insert_pos:] already starts with the newline that follows
        # `plugins {`, so don't add another one before the marker.
        content = (
            content[:insert_pos]
            + "\n"
            + GRADLE_PLUGIN_MARKER
            + "\n"
            + plugin_line
            + content[insert_pos:]
        )
    else:
        # No plugins block — prepend one
        content = (
            "plugins {\n"
            + GRADLE_PLUGIN_MARKER
            + "\n"
            + plugin_line
            + "\n}\n\n"
            + content
        )

    content += GRADLE_PLUGIN_MARKER + "\n"
    content += rewrite_block_kt if kotlin else rewrite_block_groovy

    with open(build_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[upgrade_bom] Injected OpenRewrite plugin into {build_file}")
    return True


def _remove_gradle_rewrite_plugin(build_file: str) -> None:
    """Remove the temporarily injected OpenRewrite plugin and config blocks."""
    with open(build_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned: list[str] = []
    marker_count = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if GRADLE_PLUGIN_MARKER in line:
            marker_count += 1
            if marker_count == 1:
                # First marker (inside plugins {}): skip the marker line and
                # the following injected plugin id line.
                i += 2
                continue
            else:
                # Second marker (at end of file): skip the marker and every
                # remaining line — they're the injected rewrite {} and
                # repositories {} blocks.
                break
        cleaned.append(line)
        i += 1

    with open(build_file, "w", encoding="utf-8") as f:
        f.writelines(cleaned)
    print(f"[upgrade_bom] Cleaned up OpenRewrite plugin from {build_file}")


def _run_gradle_openrewrite(gradle_cmd: str, project_dir: str) -> int:
    cmd = [gradle_cmd, "rewriteRun"]
    print(f"[upgrade_bom] Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=project_dir).returncode


def _handle_gradle(project_dir: str, bom_version: str, gradle_cmd: str | None) -> int:
    build_file = _find_gradle_build_file(project_dir)
    if build_file is None:
        print("[upgrade_bom] ERROR: no build.gradle or build.gradle.kts found", file=sys.stderr)
        return 1

    gradle = gradle_cmd or _detect_gradle(project_dir)
    has_bom = _has_gradle_bom_entry(build_file)

    if has_bom:
        print(f"[upgrade_bom] Existing azure-sdk-bom entry found — upgrading to {bom_version}.")
    else:
        print("[upgrade_bom] No existing azure-sdk-bom entry found — adding via AddPlatformDependency.")

    yml_path = None
    injected = False

    try:
        # Set up OpenRewrite: create rewrite.yml + inject plugin temporarily
        yml_path = _create_rewrite_yml(project_dir, bom_version, has_bom=has_bom)
        injected = _inject_gradle_rewrite_plugin(build_file)
        rc = _run_gradle_openrewrite(gradle, project_dir)
    finally:
        if yml_path and os.path.isfile(yml_path):
            os.remove(yml_path)
            print(f"[upgrade_bom] Removed {yml_path}")
        if injected:
            _remove_gradle_rewrite_plugin(build_file)

    if rc != 0:
        print(f"[upgrade_bom] ERROR: OpenRewrite exited with code {rc}", file=sys.stderr)
    else:
        print(f"[upgrade_bom] BOM set to {bom_version} and redundant versions removed successfully.")
    return rc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upgrade azure-sdk-bom version in a Maven or Gradle project using OpenRewrite."
    )
    parser.add_argument("project_dir", nargs="?", help="Path to the project root.")
    parser.add_argument(
        "bom_version",
        nargs="?",
        help="Optional compatibility token. Only 'latest' is accepted; explicit versions are rejected.",
    )
    parser.add_argument("--mvn", default=None, help="Maven command override.")
    parser.add_argument("--gradle", default=None, help="Gradle command override.")
    parser.add_argument(
        "--get-latest-version",
        action="store_true",
        help="Print the latest azure-sdk-bom version from the Azure SDK for Java BOM pom.xml.",
    )
    args = parser.parse_args(argv)

    if args.get_latest_version:
        if args.project_dir or args.bom_version:
            parser.error("--get-latest-version does not accept project_dir or bom_version.")
        print(_get_latest_bom_version())
        return 0

    if not args.project_dir:
        parser.error("project_dir is required unless --get-latest-version is used.")

    try:
        bom_version = _resolve_latest_bom_version(args.bom_version)
    except ValueError as exc:
        raise SystemExit(f"[upgrade_bom] ERROR: {exc}") from exc

    project_dir = os.path.abspath(args.project_dir)
    build_system = _detect_build_system(project_dir)

    if build_system == "maven":
        print("[upgrade_bom] Detected Maven project.")
        return _handle_maven(project_dir, bom_version, args.mvn)
    elif build_system == "gradle":
        print("[upgrade_bom] Detected Gradle project.")
        return _handle_gradle(project_dir, bom_version, args.gradle)
    else:
        print(
            f"[upgrade_bom] ERROR: No pom.xml or build.gradle found in {project_dir}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
