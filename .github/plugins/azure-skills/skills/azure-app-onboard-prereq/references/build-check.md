# Build Check

> ⛔ **No build/install/test commands during this check.** Use static analysis only.

Detect the project's language/framework stack and assess build health. Static detection (manifest reading) is **default**. Build execution is optional, requires user confirmation.

> **Dynamic detection:** Agent determines build commands from the project manifest (e.g., `package.json` `scripts` for the project-specific build script name). Table below is guidance, not a fixed lookup.

## Step 1: Detect Stack

Scan the workspace for project files to determine the technology stack.

| File | Language/Framework |
|------|-------------------|
| `package.json` | Node.js |
| `package.json` + `tsconfig.json` | TypeScript |
| `requirements.txt` / `pyproject.toml` | Python |
| `*.csproj` / `*.sln` | .NET |
| `pom.xml` | Java (Maven) |
| `build.gradle` / `build.gradle.kts` | Java/Kotlin (Gradle) |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `Gemfile` | Ruby |
| `composer.json` | PHP |
| `docker-compose.yml` / `compose.yml` | (dependency source — parsed during deployability check) |
| `build.gradle` + `com.google.cloud.tools.jib` | Java (Jib) |

**Modern package manager lockfiles:** `uv.lock` → uv, `bun.lock` / `bun.lockb` → bun.

> ⚠️ If **no project file** is found, check for a `Dockerfile`. If a Dockerfile exists, note container-dependent build in findings.

### Multi-Project Detection

Search recursively for project manifests, skip `node_modules`/`.git`/`dist`/`build`/`vendor`/`.venv`/`__pycache__`/`.terraform`/`bin`/`obj`. Each directory with a project file = one component.

## Step 2: Static Detection (Default)

Read project manifests to infer build health **without executing any commands**.

**Check for:** missing dependencies (imports not in manifest), version conflicts, obvious misconfigurations (missing `main`/`start` script), lock file presence.

> **Package manager detection:** `package-lock.json` → npm, `yarn.lock` → yarn, `pnpm-lock.yaml` → pnpm. Default to npm if no lockfile.

### Import → Manifest Cross-Check

Scan source files for imports not in the dependency manifest. This catches pre-existing repo bugs that cause build failures on Azure.

**Node.js/TypeScript:** Scan `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.mjs` for `import` / `require` statements. Extract package name (first path segment, `@scope/name` for scoped). Check against `dependencies` + `devDependencies`. Skip Node.js built-ins and relative paths.

**Python:** Scan `*.py` for `import {pkg}` / `from {pkg} import`, cross-reference against `requirements.txt` / `pyproject.toml`. Skip stdlib.

| File location | Severity |
|---|---|
| Build-time config (`next.config.*`, `webpack.config.*`, `vite.config.*`, `babel.config.*`, `postcss.config.*`, `tailwind.config.*`) | ❌ FAIL — build crashes at config load |
| Entry point / source — **package absent from manifest** | ❌ FAIL — `MODULE_NOT_FOUND` at runtime |
| Entry point / source — **version mismatch** | 🔧 Recommended Fix |
| Test files only | ⚠️ WARN |

**Scope:** Always scan ALL config files. For `src/`/`app/`/`pages/`/`lib/`, limit to 20 source files per component. Do NOT scan `node_modules/`, `.venv/`, `dist/`, `build/`.

**When ❌ FAIL or 🔧 Fix found:** Include in batch-then-approve: "Add `{package}` to `package.json` dependencies."

| Outcome | Verdict |
|---------|---------|
| No issues found | ✅ PASS |
| Warnings in manifest | ⚠️ WARN |
| Obvious errors | ❌ FAIL |
| No build system detected | ⚠️ WARN |
| Only Dockerfile found | ⚠️ WARN |

**Dependency vintage check:** ALL pinned deps 5+ years old AND ecosystem has known breaking changes (e.g., `werkzeug.contrib.*` removed, `flask.ext.*` removed, `itsdangerous<1.0` API changed) → ❌ FAIL. Grep for imports from removed modules.

**Transitive dependency check (post-migration):** After upgrading dependencies during 🔶 Major Migration, run install **through the build-validation gate (Step 3) — the migration-intent choice does NOT authorize install; the user must answer that specific per-command consent prompt first** to catch transitive deps. Also run entry-point import to catch import-time validation errors (e.g., WTForms `Email()` requires `email-validator`).

**F1 viability signal:** Check `f1Viable` per [dependency-compatibility.md § F1 Viability](dependency-compatibility.md). A vintage ❌ FAIL requiring 🔶 Major Migration (>5 files) → `f1Viable: false`.

## Step 3: Build Execution (Optional — User-Confirmed)

⛔ **Build-validation gate.** Before running ANY install/build/test command, ask via `ask_user`: "I'd like to run `{command}` to verify the build. Run it? (Yes / Skip)". A general prior consent (e.g., "fix my issues", "yes", "go ahead", "fix them") does NOT constitute consent — the user must answer THIS specific question with the exact command named. If they say Skip, continue with static-only verdicts.

Read manifest to determine actual build script. Install deps first. Capture output. Timeout 5 min.

| Outcome | Verdict |
|---------|---------|
| Exit code 0 | ✅ PASS |
| Succeeds with warnings | ⚠️ WARN |
| Exit code ≠ 0 | ❌ FAIL |
| Timeout >5 min | ⚠️ WARN |

## Native Module Detection

See [dependency-compatibility.md § Native Module Detection](dependency-compatibility.md) for the canonical detection procedure, edge cases, and package table. Results go to `buildRequirements.hasNativeModules`.

> ⛔ **Prebuild-install exception:** Packages with `prebuild-install` (without `node-gyp`) in lockfile use prebuilt binaries → `hasNativeModules: false`. Key examples: `better-sqlite3` v12+ = prebuilt, `sharp` v0.33+ = prebuilt, `bcrypt` = always native, `canvas` = always native. Check the lockfile — do not rely on package name alone.
