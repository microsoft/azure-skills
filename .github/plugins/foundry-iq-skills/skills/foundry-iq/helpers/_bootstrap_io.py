"""Private storage and shell-free native CLI execution for the bootstrap owner."""
from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import stat
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path

try:
    from ._common import HelperFailure, canonical_bytes
except ImportError:
    from _common import HelperFailure, canonical_bytes

MAX_BYTES = 1024 * 1024


def failure(code, message):
    return HelperFailure(code, message, blocked_at="verification")


def read_json(path):
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise failure("bootstrap-input-invalid", "JSON exceeds the one MiB input limit.")
        value = json.loads(raw.decode("utf-8"))
        pending = [(value, 0)]
        count = 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if depth > 20 or count > 10000:
                raise ValueError("JSON structure exceeds limits")
            if isinstance(item, dict):
                pending.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                pending.extend((v, depth + 1) for v in item)
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return value
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise failure("bootstrap-input-invalid", "Select bounded, valid UTF-8 JSON.") from exc


def _windows_ancestor_acl(owner_text, entries, current):
    # Windows volume roots are commonly owned by this fixed OS servicing principal.
    installer = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
    trusted = (current, "OW", "SY", "BA", installer)
    if owner_text not in tuple("O:" + trustee for trustee in trusted if trustee != "OW"):
        raise OSError("Ancestor owner can change the access boundary")
    rights = {
        "FA": 0x1F01FF, "FR": 0x120089, "FW": 0x120116, "FX": 0x1200A0,
        "GA": 0x10000000, "GR": 0x80000000, "GW": 0x40000000, "GX": 0x20000000,
        "SD": 0x10000, "RC": 0x20000, "WD": 0x40000, "WO": 0x80000,
        "CC": 1, "DC": 2, "LC": 4, "SW": 8, "RP": 16, "WP": 32, "DT": 64,
        "LO": 128, "CR": 256,
    }
    for entry in entries:
        parts = entry.split(";")
        if len(parts) != 6 or parts[0] not in ("A", "D") or parts[3] or parts[4]:
            raise OSError("Unsupported ancestor ACL")
        if parts[0] == "D" or "IO" in parts[1] or parts[5] in trusted:
            continue
        value = parts[2]
        try:
            mask = int(value, 16) if value.startswith("0x") else 0
            if not value.startswith("0x"):
                if not value or len(value) % 2:
                    raise ValueError("Unsupported rights")
                for start in range(0, len(value), 2):
                    mask |= rights[value[start:start + 2]]
        except (KeyError, ValueError) as exc:
            raise OSError("Unsupported ancestor rights") from exc
        # Delete-child, delete, write-DACL, write-owner, or generic-all can replace retained paths.
        if mask & 0x100D0040:
            raise OSError("Another principal can substitute an ancestor or its children")


def _windows_private(path, *, ancestor=False):
    # Inspect effective trustees, not chmod: Windows chmod does not establish privacy.
    from ctypes import wintypes as w
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    adv.GetNamedSecurityInfoW.argtypes = [w.LPWSTR, w.DWORD, w.DWORD] + [ctypes.POINTER(pointer)] * 5
    adv.GetNamedSecurityInfoW.restype = w.DWORD
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        pointer, w.DWORD, w.DWORD, ctypes.POINTER(w.LPWSTR), ctypes.POINTER(w.DWORD),
    ]
    adv.ConvertSidToStringSidW.argtypes = [pointer, ctypes.POINTER(w.LPWSTR)]
    adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    adv.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, pointer, w.DWORD, ctypes.POINTER(w.DWORD)]
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.LocalFree.argtypes = [pointer]
    descriptor, owner, group, dacl, sacl = (pointer() for _ in range(5))
    text, sid_text, token, size = w.LPWSTR(), w.LPWSTR(), w.HANDLE(), w.DWORD()
    try:
        if adv.GetNamedSecurityInfoW(str(path), 1, 5, ctypes.byref(owner), ctypes.byref(group),
                                    ctypes.byref(dacl), ctypes.byref(sacl), ctypes.byref(descriptor)):
            raise OSError("Cannot inspect private ACL")
        if not adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, 5, ctypes.byref(text), None,
        ):
            raise OSError("Cannot inspect security descriptor")
        if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            raise OSError("Cannot inspect current owner")
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
            raise OSError("Cannot inspect current owner")
        sid = ctypes.cast(buffer, ctypes.POINTER(pointer))[0]
        if not adv.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)):
            raise OSError("Cannot inspect current owner")
        sddl = text.value
        current = sid_text.value
        owner_text, separator, acl = sddl.partition("D:")
        if not separator or not dacl:
            raise OSError("Owner or DACL is not private")
        entries = re.findall(r"\(([^()]*)\)", acl)
        if not entries or re.sub(r"\([^()]*\)", "", acl) not in ("", "P", "AI", "PAI"):
            raise OSError("Unsupported ACL")
        if ancestor:
            _windows_ancestor_acl(owner_text, entries, current)
            return
        if owner_text != "O:" + current:
            raise OSError("Owner is not the operator")
        for entry in entries:
            parts = entry.split(";")
            if len(parts) != 6 or parts[0] != "A" or parts[5] not in (current, "OW", "SY", "BA"):
                raise OSError("ACL grants access to another principal")
    finally:
        if token:
            kernel.CloseHandle(token)
        for allocated in (descriptor, text, sid_text):
            if allocated:
                kernel.LocalFree(ctypes.cast(allocated, pointer))


def _outside_plugin(path):
    skill = Path(__file__).resolve().parents[1]
    plugin = skill.parent.parent
    protected = [skill]
    if any((plugin / marker / "plugin.json").is_file() for marker in (".plugin", ".claude-plugin", ".cursor-plugin")):
        protected.append(plugin)
    if any(root in (path.resolve(), *path.resolve().parents) for root in protected):
        raise OSError("Receipts must be outside the installed plugin")


def _safe_leaf(name):
    return (isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", name)
            and not name.endswith(".")
            and not re.fullmatch(r"(?i)(?:con|prn|aux|nul|com[1-9]|lpt[1-9])", name.split(".")[0]))


def _validated_directory(value):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise failure("bootstrap-receipt-private", "Select an absolute, existing private receipt directory.")
    path = Path(value)
    try:
        for part in (path, *path.parents):
            info = part.lstat()
            if part == path:
                selected = info
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise OSError("Linked paths are unsupported")
        _outside_plugin(path)
        if not stat.S_ISDIR(selected.st_mode):
            raise OSError("Receipt location must be a directory")
        if os.name == "nt":
            _windows_private(path)
        else:
            if selected.st_uid != os.getuid() or stat.S_IMODE(selected.st_mode) & 0o077:
                raise OSError("Directory must be private to its owner")
    except (OSError, ValueError) as exc:
        raise failure("bootstrap-receipt-private", "Receipt location must be user-owned and private; no ACLs were changed.") from exc
    return path, selected


def private_directory(value):
    return _validated_directory(value)[0]


@contextmanager
def _windows_security():
    """An explicit protected, inheritable owner/SYSTEM/admin DACL, supplied at creation."""
    from ctypes import wintypes as w
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    class Attributes(ctypes.Structure):
        _fields_ = [("length", w.DWORD), ("descriptor", pointer), ("inherit", w.BOOL)]
    adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    adv.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, pointer, w.DWORD, ctypes.POINTER(w.DWORD)]
    adv.ConvertSidToStringSidW.argtypes = [pointer, ctypes.POINTER(w.LPWSTR)]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        w.LPCWSTR, w.DWORD, ctypes.POINTER(pointer), ctypes.POINTER(w.DWORD)]
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.LocalFree.argtypes = [pointer]
    token, size, sid_text, descriptor = w.HANDLE(), w.DWORD(), w.LPWSTR(), pointer()
    try:
        if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            raise OSError("Owner unavailable")
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
            raise OSError("Owner unavailable")
        if not adv.ConvertSidToStringSidW(ctypes.cast(buffer, ctypes.POINTER(pointer))[0], ctypes.byref(sid_text)):
            raise OSError("Owner unavailable")
        sddl = f"O:{sid_text.value}D:P(A;OICI;FA;;;{sid_text.value})(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"
        if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
            raise OSError("Private descriptor unavailable")
        yield Attributes(ctypes.sizeof(Attributes), descriptor, False)
    finally:
        if token:
            kernel.CloseHandle(token)
        for allocated in (sid_text, descriptor):
            if allocated:
                kernel.LocalFree(ctypes.cast(allocated, pointer))


@contextmanager
def _pinned_directory(path, *, private=True):
    """Pin every ancestor against substitution; POSIX writes remain handle-relative."""
    handles = []
    try:
        if os.name == "nt":
            from ctypes import wintypes as w
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                          w.DWORD, w.DWORD, w.HANDLE]
            kernel.CreateFileW.restype = w.HANDLE
            kernel.CloseHandle.argtypes = [w.HANDLE]
            for part in reversed((path, *path.parents)):
                # No FILE_SHARE_DELETE: an opened ancestor cannot be renamed/replaced.
                handle = kernel.CreateFileW(str(part), 0x81, 3, None, 3, 0x02200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise OSError("Directory cannot be pinned")
                handles.append(handle)
                info = part.lstat()
                if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise OSError("Linked directory")
                _windows_private(part, ancestor=True)
            if private:
                _validated_directory(str(path))
            yield None
        else:
            if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
                raise OSError("Handle-relative creation unavailable")
            for part in reversed((path, *path.parents)):
                fd = os.open(str(part) if not handles else part.name,
                             os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                             **({"dir_fd": handles[-1]} if handles else {}))
                handles.append(fd)
                info = os.fstat(fd)
                # A foreign writable ancestor can substitute descendants, even if the leaf is 0700.
                if info.st_uid not in (0, os.getuid()) or stat.S_IMODE(info.st_mode) & 0o022:
                    raise OSError("Unsafe ancestor ownership or write access")
            if private:
                _, selected = _validated_directory(str(path))
                opened = os.fstat(handles[-1])
                if (selected.st_dev, selected.st_ino) != (opened.st_dev, opened.st_ino):
                    raise OSError("Directory identity changed")
            yield handles[-1]
    finally:
        cleanup_failed = False
        for handle in reversed(handles):
            try:
                if os.name == "nt":
                    cleanup_failed = not kernel.CloseHandle(handle) or cleanup_failed
                else:
                    os.close(handle)
            except OSError:
                cleanup_failed = True
        if cleanup_failed:
            raise OSError("Directory handle cleanup failed")


def create_private_directory(value):
    """Create one new leaf, never modify an existing directory or its ancestors."""
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise failure("bootstrap-receipt-private", "Select an absolute new private directory.")
    path = Path(value)
    try:
        if not _safe_leaf(path.name):
            raise OSError("Unsafe directory leaf")
        _outside_plugin(path)
        with _pinned_directory(path.parent, private=False) as parent_fd:
            if os.name == "nt":
                from ctypes import wintypes as w
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.CreateDirectoryW.argtypes = [w.LPCWSTR, ctypes.c_void_p]
                with _windows_security() as attributes:
                    if not kernel.CreateDirectoryW(str(path), ctypes.byref(attributes)):
                        raise OSError("Private directory creation failed")
            else:
                os.mkdir(path.name, 0o700, dir_fd=parent_fd)
            with _pinned_directory(path):
                return private_directory(str(path))
    except (OSError, ValueError, NotImplementedError) as exc:
        raise failure("bootstrap-receipt-private", "Private leaf creation failed; no existing directory ACLs were changed.") from exc


def validate_private_artifact_directory(value):
    path = private_directory(value)
    try:
        with _pinned_directory(path):
            return private_directory(value)
    except (OSError, ValueError, NotImplementedError) as exc:
        raise failure("bootstrap-receipt-private", "Private directory or ancestor stability could not be verified; no ACLs were changed.") from exc


def _windows_private_open(path, *, create=True):
    import msvcrt
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                  w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    if create:
        with _windows_security() as attributes:
            handle = kernel.CreateFileW(str(path), 0xC0010000, 1, ctypes.byref(attributes), 1, 0x80200000, None)
    else:
        handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError("Private file creation failed")
    try:
        return msvcrt.open_osfhandle(handle, (os.O_RDWR if create else os.O_RDONLY) | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise


def _windows_publish(fd, destination):
    import msvcrt
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    target = str(destination)
    size = len(target.encode("utf-16-le"))
    class Rename(ctypes.Structure):
        _fields_ = [("replace", w.BOOL), ("root", w.HANDLE), ("size", w.DWORD),
                    ("name", w.WCHAR * (size // 2 + 1))]
    value = Rename(False, None, size, target)
    kernel.SetFileInformationByHandle.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    # Rename the owned, write-through handle, never reopen a substitutable temporary pathname.
    if not kernel.SetFileInformationByHandle(msvcrt.get_osfhandle(fd), 3, ctypes.byref(value), ctypes.sizeof(value)):
        raise OSError("Private artifact publication failed")


def _cleanup_owned_temporary(directory, name, owned, *, directory_fd=None, primary=None):
    path = directory / name if directory_fd is None else name
    kwargs = {} if directory_fd is None else {"dir_fd": directory_fd}
    try:
        current = os.stat(path, follow_symlinks=False, **kwargs)
    except FileNotFoundError:
        outcome = "already-absent"
    except (OSError, NotImplementedError):
        outcome = "inspection-unavailable; entry left untouched"
    else:
        if (current.st_dev, current.st_ino) != (owned.st_dev, owned.st_ino):
            outcome = "identity-changed; entry left untouched"
        else:
            try:
                os.unlink(path, **kwargs)
                outcome = "removed"
            except FileNotFoundError:
                outcome = "already-absent"
            except (OSError, NotImplementedError):
                outcome = "removal-unconfirmed; private temporary may remain"
    warning = "Private temporary cleanup: " + outcome + "."
    if primary is not None:
        primary.warnings.append(warning)
    elif outcome not in ("removed", "already-absent"):
        error = failure("bootstrap-receipt-failed", "Private temporary cleanup could not be confirmed; no artifact success is reported.")
        error.warnings.append(warning)
        raise error
    return outcome


def atomic_private_file(directory, name, value, *, max_bytes=16 * MAX_BYTES):
    """Publish complete, verified JSON without replacing any existing filesystem entry."""
    if not _safe_leaf(name):
        raise failure("bootstrap-receipt-failed", "Artifact name must be a safe ordinary leaf.")
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                          allow_nan=False).encode("utf-8") + b"\n"
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise failure("bootstrap-receipt-failed", "Artifact must contain valid finite UTF-8 JSON.") from exc
    if len(data) > max_bytes:
        raise failure("bootstrap-receipt-failed", "Artifact exceeds its output byte bound.")
    directory = Path(directory)
    temporary = ".artifact-" + uuid.uuid4().hex
    owned = None
    primary = None
    verified = False
    try:
        with _pinned_directory(directory) as directory_fd:
            kwargs = {} if directory_fd is None else {"dir_fd": directory_fd}
            leaf = lambda name: directory / name if directory_fd is None else name
            try:
                fd = (_windows_private_open(directory / temporary) if os.name == "nt" else
                      os.open(leaf(temporary), os.O_RDWR | os.O_CREAT | os.O_EXCL |
                              os.O_NOFOLLOW, 0o600, **kwargs))
                try:
                    handle = os.fdopen(fd, "w+b")
                except BaseException:
                    os.close(fd)
                    raise
                with handle:
                    owned = os.fstat(handle.fileno())
                    if os.name == "nt":
                        _windows_private(directory / temporary)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                    handle.seek(0)
                    if handle.read() != data or os.fstat(handle.fileno()).st_nlink != 1:
                        raise OSError("Artifact integrity failed")
                    if os.name == "nt":
                        _validated_directory(str(directory))
                        _windows_publish(handle.fileno(), directory / name)
                        published = owned
                        owned = None
                        os.fsync(handle.fileno())
                # Revalidate before publication; cleanup is restricted to our original inode.
                if os.name != "nt":
                    current = os.stat(leaf(temporary), follow_symlinks=False, **kwargs)
                    if (current.st_dev, current.st_ino) != (owned.st_dev, owned.st_ino):
                        raise OSError("Artifact identity changed")
                    _validated_directory(str(directory))
                    os.link(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                            follow_symlinks=False)
                    for entry in (temporary, name):
                        current = os.stat(entry, dir_fd=directory_fd, follow_symlinks=False)
                        if (current.st_dev, current.st_ino) != (owned.st_dev, owned.st_ino):
                            raise OSError("Artifact changed during publication")
                    os.unlink(temporary, dir_fd=directory_fd)
                    published = owned
                    owned = None
                    os.fsync(directory_fd)
                fd = (_windows_private_open(directory / name, create=False) if os.name == "nt" else
                      os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd))
                try:
                    handle = os.fdopen(fd, "rb")
                except BaseException:
                    os.close(fd)
                    raise
                with handle:
                    observed = os.fstat(handle.fileno())
                    if ((observed.st_dev, observed.st_ino) != (published.st_dev, published.st_ino)
                            or not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1
                            or handle.read(len(data) + 1) != data):
                        raise OSError("Published artifact integrity failed")
                    if os.name == "nt":
                        _windows_private(directory / name)
                    _validated_directory(str(directory))
                verified = True
            except HelperFailure as exc:
                primary = exc
                raise
            except (OSError, ValueError, NotImplementedError) as exc:
                primary = failure("bootstrap-receipt-failed", "Private artifact could not be verified and persisted; no artifact success is reported.")
                raise primary from exc
            finally:
                if owned is not None:
                    try:
                        _cleanup_owned_temporary(directory, temporary, owned,
                                                 directory_fd=directory_fd, primary=primary)
                    except HelperFailure as exc:
                        primary = exc
                        raise
    except (OSError, ValueError, NotImplementedError) as exc:
        if primary is not None:
            primary.warnings.append("Private directory handle cleanup could not be confirmed.")
            raise primary from primary.__cause__
        error = failure("bootstrap-receipt-failed", "Private artifact could not be verified and persisted; no artifact success is reported.")
        if verified:
            error.warnings.append("Private directory handle cleanup could not be confirmed.")
        raise error from exc
    return directory / name


def private_file(directory, name, value):
    return private_bytes(directory, name, canonical_bytes(value) + b"\n")


def private_bytes(directory, name, data):
    if not _safe_leaf(name):
        raise failure("bootstrap-receipt-failed", "Receipt name must be a safe, ordinary leaf name.")
    if not isinstance(data, bytes):
        raise failure("bootstrap-receipt-failed", "Private content must be bounded bytes.")
    if len(data) > MAX_BYTES:
        raise failure("bootstrap-receipt-failed", "Sanitized receipt exceeds its bound.")
    directory_fd = file_fd = None
    primary = None
    try:
        directory, selected = _validated_directory(str(directory))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        if os.name == "nt":
            file_fd = os.open(directory / name, flags, 0o600)
        else:
            if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
                raise failure("bootstrap-receipt-private", "POSIX handle-relative private creation is unavailable.")
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            opened = os.fstat(directory_fd)
            if ((opened.st_dev, opened.st_ino) != (selected.st_dev, selected.st_ino)
                    or not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.getuid()
                    or stat.S_IMODE(opened.st_mode) & 0o077):
                raise failure("bootstrap-receipt-private", "Opened receipt directory changed identity, ownership or permissions.")
            file_fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
        handle = os.fdopen(file_fd, "wb")
        file_fd = None
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except HelperFailure as exc:
        primary = exc
        raise
    except (OSError, NotImplementedError) as exc:
        primary = failure("bootstrap-receipt-failed", "Private receipt could not be persisted; retain the returned ownership handoff.")
        raise primary from exc
    finally:
        cleanup_failed = False
        for descriptor in (file_fd, directory_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    cleanup_failed = True
        if cleanup_failed:
            if primary is not None:
                primary.warnings.append("Receipt descriptor cleanup could not be confirmed.")
            else:
                raise failure("bootstrap-receipt-failed", "Receipt descriptor cleanup could not be confirmed.")
    return directory / name


def cli_prefix():
    executable = shutil.which("az")
    if executable is None:
        raise failure("bootstrap-tool-unavailable", "A signed-in Azure CLI installation is required.")
    if os.name == "nt":
        if Path(executable).suffix.lower() not in (".cmd", ".bat"):
            raise failure("bootstrap-tool-unavailable", "Windows requires the supported bundled CLI Python layout.")
        # Use the installed CLI's own interpreter, never cmd.exe or caller commands.
        # Azure/azure-cli: build_scripts/windows/scripts/az_msi.cmd (and az_zip.cmd).
        python = Path(executable).parent.parent / "python.exe"
        if not python.is_file():
            raise failure("bootstrap-tool-unavailable", "This Windows CLI layout has no supported bundled Python launcher.")
        return [str(python), "-IBm", "azure.cli"]
    return [executable]


def run_cli(arguments, timeout):
    """Capture native CLI output; size validation is post-capture, not a memory bound."""
    env = dict(os.environ, AZURE_EXTENSION_USE_DYNAMIC_INSTALL="no",
               AZURE_CORE_COLLECT_TELEMETRY="no", AZURE_CORE_ONLY_SHOW_ERRORS="true",
               AZURE_CORE_NO_COLOR="true", AZURE_LOGGING_ENABLE_LOG_FILE="false",
               AZURE_AUTO_UPGRADE_ENABLE="false")
    try:
        command = cli_prefix() + arguments + ["--output", "json", "--only-show-errors"]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                shell=False, env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise failure("bootstrap-cli-timeout", "Native CLI timed out; remote completion and process-tree cleanup are not established.") from exc
    except OSError as exc:
        cause = exc
        for _ in range(8):
            if not isinstance(cause, OSError):
                break
            cause = cause.__context__
        if isinstance(cause, subprocess.TimeoutExpired):
            error = failure("bootstrap-cli-timeout", "Native CLI timed out; remote completion is not established.")
            error.warnings.append("Standard subprocess cleanup also failed; process state is unknown.")
        else:
            error = failure("bootstrap-cli-unavailable", "Native CLI execution failed; process and remote state may be unknown.")
        raise error from exc
    if len(result.stdout) > MAX_BYTES or len(result.stderr) > MAX_BYTES:
        raise failure("bootstrap-cli-output-limit", "Captured CLI output exceeds one MiB per stream; this is not a capture-memory bound.")
    return result.returncode, result.stdout, result.stderr
