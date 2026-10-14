# Source Code Windows Dependency Scan

> **When**: Phase 1 Assessment, after [Step 2f](automation/discovery-and-assessment.md#2f-check-blob-storage-triggers), as **[Step 2g](automation/discovery-and-assessment.md#2g-source-code-windows-dependency-scan)**. **Always recommended, never required.** If the user skips, proceed — they own the runtime risk.

## What This Scan Does

Walks the source tree for code, config, and packaging patterns that depend on Windows. Prefer source code because project manifests and API usage are directly inspectable. Use the deployed package from [Step 3e](automation/deployment-package.md#3e-get-deployment-package-if-needed) only when source is unavailable; it confirms what is running but may contain compiled artifacts that reduce scan coverage. Findings populate **§11** of the assessment report; ≥1 `Blocker` finding advisorily flips **§1 Upgrade Readiness** to `Needs Attention` (never hard-blocks).

> ⚠️ **Heuristic aid, not a guarantee.** This scan pattern-matches the most common Windows-only APIs, packages, RID targeting, and shell-outs to Windows tools. It is **not exhaustive** — uncommon Windows APIs, dynamically-loaded DLLs, transitive package dependencies, reflection-based calls, and runtime-generated code can slip past. **The app owner is ultimately responsible for verifying their code has no Windows dependencies.** False negatives are dangerous; false positives create friction. The scan's job is to **inform**, not gate.

## Inputs

1. **Source location** — use `ask_user` to explicitly request a local source directory or checked-out repository path; do not infer that the current workspace contains the function app. Explain that source provides the best scan coverage. If the user cannot provide source, offer the deployed package from Step 3e as a fallback. If they decline both, write "scan skipped" to §11 and stop.
2. **Language** — auto-dispatched from `FUNCTIONS_WORKER_RUNTIME` (captured in [Step 2b](automation/discovery-and-assessment.md#2b-verify-language-stack-compatibility)). Always run the agnostic set + the matching per-language set.
3. **`custom` worker** — agnostic set only; ask once if the handler is C#, Node, Java, Python, or PowerShell source and layer in that set if so.

## Categories

| # | Category |
|---|----------|
| 1 | Win32 / WinRT / COM / WMI APIs |
| 2 | Path / case / line-ending / env-var assumptions |
| 3 | Windows certificate store |
| 4 | Windows registry |
| 5 | Windows-only packages |
| 6 | Windows-RID / `net4x` targeting |
| 7 | Windows-only PowerShell modules |
| 8 | Shelling out to Windows tools |

## Finding Severity

| Severity | Meaning | Effect on §1 |
|----------|---------|-------------|
| 🛑 **Blocker** | Will definitely fail on Linux (e.g. `[DllImport("kernel32.dll")]`, `Microsoft.Win32.Registry`, `System.Drawing.Common` on .NET 6+, `.exe` handler for `custom` worker) | `Needs Attention` (advisory) |
| ⚠️ **Likely** | Often breaks but may be guarded (backslash paths, drive letters, RID-specific package refs) | None |
| ℹ️ **Review** | Heuristic worth a human eye (any P/Invoke, any external `Process.Start`, package name containing `Windows`) | None |

## How to Read These Patterns

Each bullet below states a **principle** followed by anchor examples. Treat the examples as starting points, not as an exhaustive whitelist — when you encounter similar patterns that aren't enumerated (a different system DLL, a different `System.*` namespace prefix, a different Windows admin exe, a different Windows-only PowerShell module, a different `win32`-flavored npm package name), flag them under the same category. The category headers in **bold** are the rule; the examples after the em-dash are how that rule commonly shows up.

## Language-Agnostic Patterns

Run for every worker runtime. Cite the category number on each finding.

- **(2) Windows path / env-var literals** — path-like strings with a drive letter (`@"C:\..."`, `"D:\\..."`) or Windows env-var references in the `%FOO%` shape (`%TEMP%`, `%USERPROFILE%`, `%WINDIR%`, `%PROGRAMFILES%`, `%APPDATA%`, `%LOCALAPPDATA%`, …).
- **(2) CRLF-dependent parsing** — `Split("\r\n")`, byte-exact file reads, anything that hard-codes `\r\n` line endings.
- **(8) Spawning a Windows-only executable** — language-specific syntax varies (see per-language), but the executable is one of: `cmd`, `powershell`/`pwsh`, `cscript`, `wscript`, `reg`, `wmic`, `tasklist`, `net`, `sc`, `iisreset`, `netsh`, `wevtutil`, or any path ending `.exe`/`.bat`/`.cmd`/`.ps1`.
- **(8) Windows device / pipe paths** — paths starting with `\\.\` (devices, named pipes), `\\?\` (Win32 long-path namespace), or `\\.\pipe\` specifically. No Linux equivalent.
- **(6) Windows-RID in build/deploy config** — `.csproj`/`.fsproj`/`launchSettings.json`/`Dockerfile`/pipeline yaml referencing `win-x64`, `win-x86`, `win-arm64`, or `win10-*` outside a Windows-only condition.
- **(6) Windows-only `runtimes/win-*/` payload** — deployment package contains `runtimes/win-*/` without a matching `runtimes/linux-x64/`.

## Per-Language Patterns

### `dotnet-isolated`

- **(1) Win32 P/Invoke** — `[DllImport("<dll>")]` of any Windows system DLL: `kernel32`, `user32`, `advapi32`, `ole32`, `gdi32`, `shell32`, `ntdll`, `wininet`, `crypt32`, etc.
- **(1) Windows-only .NET namespaces** — `using` directives, fully-qualified type names, or `PackageReference` whose namespace prefix exists only to wrap Windows. Match the **prefix**, not the leaf type. Known prefixes: `System.Drawing.*` (GDI+), `System.DirectoryServices.*` (ADSI/LDAP), `System.Management.*` (WMI), `Microsoft.Win32.*` (registry, scheduler), `System.ServiceProcess.*` (Windows services), `Microsoft.Office.Interop.*`.
- **(1) COM activation** — `[ComImport]`, `Marshal.GetActiveObject`, `Type.GetTypeFromProgID` / `…FromCLSID`, `Activator.CreateInstance` of a COM type, or string-literal ProgIDs (`WScript.Shell`, `Excel.Application`, `Word.Application`, …).
- **(3) Windows certificate store** — `X509Store(StoreLocation.LocalMachine | CurrentUser)`. Linux uses an OpenSSL-backed store; behavior differs even where the API exists.
- **(4) Windows registry** — anything under `Microsoft.Win32.Registry*` (`Registry.LocalMachine`, `Registry.CurrentUser`, `Registry.ClassesRoot`, `RegistryKey.*`).
- **(5) Windows-only NuGet packages** — `<PackageReference>` id matching `*Windows*`, `*.Win32*`, or `*.Office.Interop.*`. Specific offenders: `System.Drawing.Common`, `System.Management`, `System.DirectoryServices.AccountManagement`, `Microsoft.Windows.Compatibility`, `WindowsAzure.Storage`.
- **(6) Windows-RID targeting** — `<RuntimeIdentifier>` / `<RuntimeIdentifiers>` containing any `win-*` (`win-x64`, `win-x86`, `win-arm64`, `win10-*`) without a matching `linux-*`.
- **(6) `net4x` target framework** — `<TargetFramework[s]>` containing `net4` (also in [Known Limitations](workflow.md#known-limitations-and-migration-blockers)).
- **(8) Shelling out to a Windows-only tool** — `Process.Start(...)` / `new ProcessStartInfo(...)` whose executable matches the agnostic Windows-tool list.

### `node`

- **(1) Windows-only npm packages** — `require`/`import` of packages whose purpose is wrapping Windows. Naming patterns: `node-windows-*`, `windows-*`, `win32-*`. Known: `node-windows`, `windows-shortcuts`, `windows-foreground-love`, `node-task-scheduler`, `edge`/`edge-js` (CLR bridge), `regedit`.
- **(5) Windows-only npm dependencies** — `package.json` deps matching the naming patterns above, or `os: ["win32"]` (refuses to install on Linux), or `cpu` constraints excluding Linux arches.
- **(6) Pre-built Windows native add-ons** — `node_modules/**/*.node` files that are PE-format. Any `.node` shipped without a Linux-built equivalent fails to load. Solution: rebuild on Linux at deploy time.
- **(8) Shelling out to a Windows-only tool** — `child_process.exec`/`spawn`/`execSync` whose command matches the agnostic Windows-tool list.

### `java`

- **(1) Windows-only Java APIs** — `import` of namespaces wrapping Windows: `com.sun.jna.platform.win32.*`, `com.jacob.*` (COM bridge), `org.eclipse.swt.win32.*`, anything ending in `.win32`. Also flag `System.loadLibrary` / `System.load` whose argument resolves to a `.dll`.
- **(5) Windows-only Maven/Gradle deps** — `pom.xml` / `build.gradle` entries whose `groupId:artifactId` contains `windows`, `win32`, or `jacob`. Anchors: `com.sun.jna:jna-platform`, `net.sf.jacob-project:jacob`, `org.eclipse.swt.win32.*`.
- **(6) Bundled Windows native binaries** — `.dll` files under `src/main/resources/`, `META-INF/native/`, or shaded into the jar — won't load on Linux even if the calling Java is portable.
- **(8) Shelling out to a Windows-only tool** — `Runtime.exec(...)` / `new ProcessBuilder(...)` whose command matches the agnostic Windows-tool list.

### `python`

- **(1) Windows-only Python modules** — `import` of any module in the `win32*` family (`win32api`, `win32com`, `win32con`, `win32event`, `win32file`, `win32process`, `win32security`, …), the registry interfaces (`winreg`, `_winreg`), or COM/WMI bridges (`pythoncom`, `wmi`, `pywinauto`, `comtypes`, `pythonnet`).
- **(1) Win32 via ctypes** — `ctypes.windll.*`, `ctypes.WinDLL(...)`, `ctypes.OleDLL(...)`. The `ctypes.windll` attribute itself only exists on Windows Python.
- **(5) Windows-only pip dependencies** — `requirements.txt` / `pyproject.toml` / `Pipfile` entries whose name signals Windows-only (`pywin32`, `pywinauto`, `wmi`, `winshell`, `pythonnet`, `comtypes`, `win32-*`) or pinned via `sys_platform == 'win32'` environment marker without an alternate branch.
- **(8) Shelling out to a Windows-only tool** — `subprocess.run`/`Popen`/`call` or `os.system` whose command matches the agnostic Windows-tool list.

### `powershell`

- **(1, 7) WMI / CIM cmdlets** — `Get-WmiObject`, `Get-CimInstance`, `Invoke-WmiMethod`, `Invoke-CimMethod`. PowerShell 7 on Linux silently returns `null` instead of erroring — failures are easy to miss.
- **(1) COM activation & Windows-only providers** — `New-Object -ComObject …`, `Get-EventLog`, Windows-service form of `Get-Service`/`*-Service`, anything in `Microsoft.PowerShell.LocalAccounts`.
- **(4, 7) Registry cmdlets / provider paths** — any access to the `Registry::` provider: `Get-ItemProperty Registry::*`, `Get-ChildItem HKLM:` / `HKCU:` / `HKCR:`, `Set-ItemProperty -Path HKLM:\…`, `New-PSDrive -PSProvider Registry`.
- **(7) Windows-only modules** — `Import-Module` of modules shipped only with Windows PowerShell, RSAT, or a Windows feature. Anchors: `ActiveDirectory`, `GroupPolicy`, `ServerManager`, `Hyper-V`, `BitsTransfer`, `ScheduledTasks`, `MSOnline`, `AzureAD`, `Dism`.
- **(3) Windows certificate store** — paths under `Cert:\LocalMachine\*` or `Cert:\CurrentUser\*`. Linux PowerShell has a limited read-only implementation.
- **(7) `requirements.psd1` `RequiredModules`** — pinning any module above.
- **(8) Shelling out to a Windows-only tool** — `& cmd.exe …`, `Start-Process` of a Windows binary, `Invoke-Expression` of any Windows admin command line.

### `go`

- **(1) Windows-only Go APIs** — imports of `golang.org/x/sys/windows` or calls to `syscall.NewLazyDLL`, `windows.NewLazySystemDLL`, or other Windows DLL-loading APIs.
- **(5, 6) Windows-only build constraints** — required source files named `*_windows.go`, `//go:build windows` constraints without a Linux implementation, or build/deployment configuration that sets `GOOS=windows`.
- **(6) Windows handler binaries** — deployed `.exe` or PE-format handler binaries without a Linux ELF equivalent.
- **(8) Shelling out to a Windows-only tool** — `os/exec.Command` or `CommandContext` whose executable matches the agnostic Windows-tool list.

### `custom`

Run the agnostic set, plus:

- **(6) Handler binary is a Windows PE** — `file <handler>` reports `PE32+ executable … for MS Windows` → 🛑 Blocker (must be rebuilt for Linux).
- **(6) Bundled Windows native deps** — `.dll` files in the package without matching `.so` / Linux ELF.
- **(8) Windows-script handler entry-point** — `host.json` `customHandler.description.defaultExecutablePath` ending in `.exe`, `.bat`, `.cmd`, or `.ps1`.

If the user identifies the handler's source language as one of the supported seven, also layer in that set.

## Output

Each finding:

```yaml
- category: 1-8
  severity: blocker | likely | review
  file: <relative path>
  line: <line number, if applicable>
  match: <the matched code or setting>
  remediation: <one-line fix or "Migrate to Elastic Premium on Windows">
```

Findings populate **§11 Source Code Windows Dependency Scan** of the assessment report — see the template in [assessment.md](assessment.md#assessment-report-format). If the user declined the scan, write *"User declined the source code dependency scan. Migration proceeded without static analysis of Windows dependencies."* in place of the findings table.
