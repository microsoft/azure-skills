"""OS-enforced limits installed in the document worker before parser imports."""
from __future__ import annotations

import os
import sys

MEMORY_BYTES = 256 * 1024 * 1024
CPU_SECONDS = 10


def install_limits():
    """Return a live Windows job handle, or None on Linux; fail closed elsewhere."""
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        return None
    if sys.platform != "win32":
        raise OSError("unsupported limit platform")

    import ctypes
    from ctypes import wintypes as w

    class Basic(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
            ("flags", w.DWORD), ("min_ws", ctypes.c_size_t),
            ("max_ws", ctypes.c_size_t), ("active", w.DWORD),
            ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
            ("scheduling", w.DWORD),
        ]

    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ("read_ops", "write_ops", "other_ops", "read_bytes",
                     "write_bytes", "other_bytes")]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
            ("peak_job", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int,
                                               ctypes.c_void_p, w.DWORD]
    kernel.SetInformationJobObject.restype = w.BOOL
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.AssignProcessToJobObject.restype = w.BOOL
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Extended()
    # PROCESS_TIME | ACTIVE_PROCESS | PROCESS_MEMORY | KILL_ON_JOB_CLOSE.
    limits.basic.flags = 0x2 | 0x8 | 0x100 | 0x2000
    limits.basic.process_time = CPU_SECONDS * 10_000_000
    limits.basic.active = 1
    limits.process_memory = MEMORY_BYTES
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits),
                                          ctypes.sizeof(limits)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(job)
        raise ctypes.WinError(error)
    if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
        error = ctypes.get_last_error()
        kernel.CloseHandle(job)
        raise ctypes.WinError(error)
    # Keep the handle until process exit: closing it terminates this worker.
    return job


def deny_side_effects(event, args):
    """Defense in depth, not a sandbox for arbitrary Python/native code."""
    if event.startswith("socket.") or event in {
        "subprocess.Popen", "os.system", "os.posix_spawn", "os.fork",
        "os.remove", "os.unlink", "os.rename", "os.replace", "os.mkdir", "os.rmdir",
        "os.truncate", "os.chmod", "os.chown", "os.lchown", "os.utime",
        "os.link", "os.symlink", "os.chflags", "os.setxattr", "os.removexattr",
    }:
        raise PermissionError("Document side effect denied")
    if event == "open":
        _, mode, flags = args
        if (mode and any(char in mode for char in "wax+")) or (
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        ):
            raise PermissionError("Document write denied")
