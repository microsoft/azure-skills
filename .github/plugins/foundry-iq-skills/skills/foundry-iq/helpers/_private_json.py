"""Bounded private JSON evidence reader shared by retained-operation workflows."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

try:
    from . import _bootstrap_io as private_io
except ImportError:
    import _bootstrap_io as private_io


def _json(raw):
    def unique(pairs):
        value = {}
        for key, child in pairs:
            if key in value:
                raise ValueError("Duplicate field")
            value[key] = child
        return value
    try:
        value = json.loads(raw, object_pairs_hook=unique)
        json.dumps(value, allow_nan=False, ensure_ascii=False).encode("utf-8")
        if not isinstance(value, dict):
            raise ValueError("Expected object")
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise private_io.failure("recheck-evidence-invalid", "Retain bounded, unmodified UTF-8 object evidence.") from exc


def read_private(path):
    path = Path(path)
    private_io.private_directory(str(path.parent))
    try:
        selected = path.lstat()
        if (not stat.S_ISREG(selected.st_mode) or selected.st_nlink != 1
                or getattr(selected, "st_file_attributes", 0) & 0x400):
            raise OSError("Not an ordinary private file")
        if os.name == "nt":
            private_io._windows_private(path)
        elif selected.st_uid != os.getuid() or stat.S_IMODE(selected.st_mode) & 0o077:
            raise OSError("Not private")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            handle = os.fdopen(descriptor, "rb")
        except BaseException as error:
            try:
                os.close(descriptor)
            except OSError:
                error.add_note("Private evidence descriptor cleanup could not be confirmed.")
            raise
        with handle:
            opened = os.fstat(handle.fileno())
            if (selected.st_dev, selected.st_ino) != (opened.st_dev, opened.st_ino):
                raise OSError("Evidence changed identity")
            raw = handle.read(private_io.MAX_BYTES + 1)
        if len(raw) > private_io.MAX_BYTES:
            raise OSError("Evidence exceeds bound")
        return _json(raw.decode("utf-8"))
    except (OSError, UnicodeError) as exc:
        raise private_io.failure("recheck-evidence-unreadable", "Select existing private, unlinked evidence files; no permissions were changed.") from exc
