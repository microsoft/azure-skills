"""Opt-in private unapproved execution artifacts; no Azure or approval operations."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

try:
    from . import _bootstrap_io as private_io
    from ._common import HelperFailure, blocked_result, canonical_bytes, digest, emit_result, reject_secrets
except ImportError:
    import _bootstrap_io as private_io
    from _common import HelperFailure, blocked_result, canonical_bytes, digest, emit_result, reject_secrets


def add_execution_output_argument(parser):
    parser.add_argument("--execution-output", type=Path,
                        help="With --plan only: write exact UNAPPROVED input to a new absolute private file.")


def validate_execution_output_mode(args):
    if args.execution_output is not None and not args.plan:
        raise private_io.failure("planning-output-invalid", "--execution-output requires --plan.")


def retain_execution_input(document, output):
    """Extension contract: pass the exact closed envelope, never a redacted wrapper."""
    try:
        if (not isinstance(document, dict) or set(document) != {"schema_version", "plan", "approval"}
                or document["schema_version"] not in ("1.0", "2.0")
                or not isinstance(document["plan"], dict)
                or document["approval"] != {"confirmed": False, "fingerprint": digest(document["plan"])}
                or document["approval"]["confirmed"] is not False):
            raise ValueError("Unapproved envelope required")
        reject_secrets(document)
        path = Path(output)
        if not path.is_absolute():
            raise ValueError("Absolute output required")
    except (HelperFailure, TypeError, ValueError, RecursionError) as exc:
        raise private_io.failure("planning-output-invalid", "Select an absolute private output and an exact unapproved, secret-free execution input.") from exc
    written = private_io.atomic_private_file(
        path.parent, path.name, document,
        max_bytes=private_io.MAX_BYTES * (1 if document["schema_version"] == "2.0" else 16))
    return {
        "path": str(written),
        "sha256": hashlib.sha256(canonical_bytes(document) + b"\n").hexdigest(),
        "fingerprint": document["approval"]["fingerprint"],
        "confirmed": False,
    }


def emit_plan_result(result, execution_output=None, *, preserve_unapproved_input=False):
    if execution_output is None:
        emit_result(result, preserve_unapproved_input=preserve_unapproved_input)
        return
    if result.get("status") != "planned":
        emit_result(result)
        return
    reference = retain_execution_input(result.get("execution_input"), execution_output)
    # Copy only fixed booleans/counts: arbitrary summaries contain names, queries and private text.
    original = result.get("approval_summary")
    original = original if isinstance(original, dict) else {}
    summary = {}
    for key in ("execution_required", "mutation_approval_required"):
        if type(original.get(key)) is bool:
            summary[key] = original[key]
    boundary = original.get("data_boundary")
    boundary = boundary if isinstance(boundary, dict) else {}
    for key in ("file_count", "object_count", "total_bytes", "uploads", "queries"):
        value = original.get(key, boundary.get(key))
        if type(value) is int and 0 <= value <= 2**63 - 1:
            summary[key] = value
    emit_result({
        "status": "planned", "execution_artifact": reference,
        "summary": summary,
        "next_step": "Review the private artifact. Execute only if required, after separate approval.",
        "local_filesystem": {"artifact_created": True, "existing_files_changed": False},
        "azure_mutation_performed": False,
    })


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create one new private leaf or validate an existing private receipt directory; local only.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--create-directory")
    modes.add_argument("--validate-directory")
    args = parser.parse_args(argv)
    try:
        path = (private_io.create_private_directory(args.create_directory) if args.create_directory else
                private_io.validate_private_artifact_directory(args.validate_directory))
        emit_result({"status": "ready", "private_directory": str(path),
                     "local_filesystem": {"directory_created": args.create_directory is not None,
                                          "existing_acls_changed": False},
                     "azure_calls_performed": False, "approval_granted": False})
        return 0
    except HelperFailure as error:
        emit_result(blocked_result(error, outcome="private-artifact-directory", fingerprint=None))
        return 2


if __name__ == "__main__":
    sys.exit(main())
