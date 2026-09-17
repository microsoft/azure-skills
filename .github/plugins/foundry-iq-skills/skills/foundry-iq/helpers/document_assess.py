"""Consent-gated input-document structural facts; never emit document content."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading

PARSER_VERSION = "6.8.0"
MAX_INPUT = 16 * 1024 * 1024
MAX_PAGES = 200
MAX_SELECTED = 8
MAX_OUTPUT = 8192
MAX_REQUEST = 16384
WALL_SECONDS = 15
FORMATS = {"auto", "pdf", "text", "markdown", "html", "json", "docx", "pptx",
           "xlsx", "png", "jpeg"}


class Blocked(ValueError):
    """A public, content-free blocker code."""


def blocked(code):
    return {"schema_version": "1.0", "status": "blocked", "assessment": "not-assessed", "code": code,
            "service_admission": "not-assessed", "facts": None}


def validate_request(request):
    if not isinstance(request, dict) or request.get("approved") is not True:
        raise Blocked("inspection-not-approved")
    if not {"approved", "path", "sha256"} <= set(request) or set(request) - {
        "approved", "path", "sha256", "pages", "whole_document", "format"
    }:
        raise Blocked("invalid-request")
    path, digest, pages = request["path"], request["sha256"], request.get("pages")
    if isinstance(path, str) and path.lower().startswith(("http:", "https:", "abfs:", "abfss:")):
        raise Blocked("remote-sample-access-not-supported")
    if (not isinstance(path, str) or len(path) > 4096 or "\0" in path
            or not Path(path).is_absolute()):
        raise Blocked("invalid-source-path")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise Blocked("invalid-source-identity")
    if (pages is not None and (not isinstance(pages, list) or not 1 <= len(pages) <= MAX_SELECTED
            or any(type(page) is not int or not 1 <= page <= MAX_PAGES for page in pages)
            or len(set(pages)) != len(pages))):
        raise Blocked("invalid-page-selection")
    if type(request.get("whole_document", False)) is not bool or (
        (pages is not None) == request.get("whole_document", False)
    ):
        raise Blocked("explicit-document-scope-required")
    if not isinstance(request.get("format", "auto"), str) or request.get("format", "auto") not in FORMATS:
        raise Blocked("unsupported-format-hint")


def read_source(request):
    path = Path(request["path"])
    if sys.platform == "win32":
        import ctypes

        # Reject device namespaces, UNC, ADS and mapped network drives.
        if (str(path).startswith("\\\\") or ":" in str(path)[2:]
                or ctypes.windll.kernel32.GetDriveTypeW(str(path.anchor)) not in (3, 6)):
            raise Blocked("nonlocal-source")
    if any(item.is_symlink() or (
        getattr(item.lstat(), "st_file_attributes", 0) & 0x400
    ) for item in (path, *path.parents)):
        raise Blocked("source-link-unsupported")
    canonical = path.resolve(strict=True)
    with canonical.open("rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise Blocked("nonregular-source")
        if before.st_size > MAX_INPUT:
            raise Blocked("input-limit")
        data = source.read(MAX_INPUT + 1)
        after = os.fstat(source.fileno())
    if len(data) > MAX_INPUT:
        raise Blocked("input-limit")
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ) or len(data) != before.st_size:
        raise Blocked("source-changed")
    if hashlib.sha256(data).hexdigest() != request["sha256"]:
        raise Blocked("source-identity-mismatch")
    binding = hashlib.sha256(os.path.normcase(str(canonical)).encode("utf-8")).hexdigest()
    return data, binding


def deny_document_reads(event, args):
    if event in {"open", "os.listdir", "os.scandir"}:
        raise PermissionError("Document external read denied")


def assess_bytes(data, selected):
    import codecs
    import logging
    import warnings

    try:
        import pypdf
    except ImportError:
        raise Blocked("parser-dependency-missing") from None
    if pypdf.__version__ != PARSER_VERSION:
        raise Blocked("parser-version-unsupported")
    from pypdf.errors import PdfReadError, PdfStreamError
    from pypdf.generic import ContentStream

    class RejectWarning(logging.Handler):
        def emit(self, record):
            raise Blocked("pdf-parser-warning")

    logger = logging.getLogger("pypdf")
    logger.handlers = [RejectWarning()]
    logger.propagate = False
    logger.setLevel(logging.WARNING)
    warnings.simplefilter("error")
    for encoding in ("charmap", "utf-16-be", "utf-16-le", "utf-8", "latin-1", "ascii"):
        codecs.lookup(encoding)
    # Parser imports are trusted installation reads; once bytes are supplied,
    # no PDF-directed file read (even local) is permitted.
    sys.addaudithook(deny_document_reads)
    if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        raise Blocked("invalid-pdf")
    try:
        reader = pypdf.PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise Blocked("encrypted-pdf")
        page_count = len(reader.pages)
        if page_count > MAX_PAGES:
            raise Blocked("page-limit")
        if max(selected) > page_count:
            raise Blocked("page-out-of-range")
        pages = []
        for number in selected:
            page = reader.pages[number - 1]
            # Direct stream operators, not object inventory or rendered entities.
            content = page.get_contents()
            operations = ContentStream(content, reader).operations if content is not None else []
            images, drawings, forms = 0, 0, 0
            for operands, operator in operations:
                if operator == b"INLINE IMAGE":
                    images += 1
                elif operator in {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}:
                    drawings += 1
                elif operator == b"Do":
                    obj = page["/Resources"]["/XObject"][operands[0]].get_object()
                    subtype = obj["/Subtype"]
                    if subtype == "/Image":
                        images += 1
                    elif subtype == "/Form":
                        forms += 1
                    else:
                        raise Blocked("unsupported-paint-object")
            # Forms can reference other pages/resources. Do not traverse them to
            # estimate modality; report text unknown instead of widening scope.
            characters = None if forms else len(page.extract_text())
            pages.append({
                "page": number,
                "text_characters": characters,
                "text_available": None if characters is None else characters > 0,
                "text_status": "not-assessed-form-content" if forms else "assessed",
                "direct_image_paints": images,
                "direct_path_paints": drawings,
                "form_invocations": forms,
                "total_images": None,
                "total_drawings": None,
                "table_structure": "not-assessed",
                "layout_relationships": "not-assessed",
            })
        return {"page_count": page_count, "pages": pages, "input_profile": "unknown",
                "answerability": "not-assessed", "ocr_need": "not-assessed"}
    except (PdfReadError, PdfStreamError, KeyError, IndexError, TypeError,
            UnicodeError, NotImplementedError):
        raise Blocked("pdf-parse-unsupported") from None
    except Warning:
        raise Blocked("pdf-parser-warning") from None
    except PermissionError:
        raise Blocked("pdf-external-read-blocked") from None


def dispatch(data, request):
    hint = request.get("format", "auto")
    if data.startswith(b"%PDF-"):
        if hint not in {"auto", "pdf"}:
            raise Blocked("format-hint-mismatch")
        if request.get("pages") is None:
            raise Blocked("pdf-page-selection-required")
        return "pdf", f"pypdf=={PARSER_VERSION}", assess_bytes(data, request["pages"])
    if request.get("pages") is not None:
        raise Blocked("non-pdf-requires-whole-document-scope")
    from _document_adapters import AdapterBlocked, assess_document

    try:
        return assess_document(data, hint, deny_document_reads)
    except AdapterBlocked as error:
        raise Blocked(str(error)) from None


def worker():
    # Isolated mode excludes ambient PYTHONPATH; add only this packaged helper.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _document_limits import deny_side_effects, install_limits

    try:
        job_handle = install_limits()
    except (OSError, ValueError):
        return blocked("worker-limits-unavailable")
    sys.addaudithook(deny_side_effects)
    binding = {}
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            raise Blocked("request-limit")
        request = json.loads(raw)
        validate_request(request)
        data, path_digest = read_source(request)
        binding = {"source_sha256": request["sha256"], "path_sha256": path_digest}
        kind, parser, facts = dispatch(data, request)
        return {"schema_version": "1.0", "status": "completed", "assessment": "assessed",
                "service_admission": "not-assessed", "format": kind, "parser": parser,
                **binding, "facts": facts}
    except Blocked as error:
        return dict(blocked(str(error)), **binding)
    except MemoryError:
        return dict(blocked("worker-memory-limit"), **binding)
    except RecursionError:
        return dict(blocked("document-recursion-limit"), **binding)
    except (OSError, ValueError, OverflowError):
        return dict(blocked("document-input-or-parse-failed"), **binding)
    finally:
        # This local deliberately remains live through parsing on Windows.
        _ = job_handle


def run_worker(command, request, timeout=WALL_SECONDS):
    """Pipe-only IPC; bounded output reader, no sample or stderr artifacts."""
    encoded = json.dumps(request, separators=(",", ":")).encode()
    if len(encoded) > MAX_REQUEST:
        return blocked("request-limit")
    output = bytearray()
    exceeded = threading.Event()
    io_failed = threading.Event()
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL) as process:
        def drain():
            try:
                chunk = process.stdout.read(MAX_OUTPUT + 1)
                if len(chunk) > MAX_OUTPUT:
                    exceeded.set()
                    process.kill()
                else:
                    output.extend(chunk)
            except OSError:
                io_failed.set()

        def send():
            try:
                process.stdin.write(encoded)
                process.stdin.close()
            except OSError:
                io_failed.set()

        thread = threading.Thread(target=drain, daemon=True)
        writer = threading.Thread(target=send, daemon=True)
        thread.start()
        writer.start()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            return blocked("worker-timeout")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            thread.join()
            writer.join()
        if exceeded.is_set():
            return blocked("worker-output-limit")
        if process.returncode not in (0, 2):
            return blocked("worker-failed-or-resource-limit")
        if io_failed.is_set():
            return blocked("worker-io-failed")
    try:
        result = json.loads(output)
    except (ValueError, UnicodeError):
        return blocked("worker-invalid-output")
    if not isinstance(result, dict) or result.get("status") not in {"completed", "blocked"}:
        return blocked("worker-invalid-output")
    return result


def assess(request):
    try:
        validate_request(request)
        return run_worker([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                           "--worker"], request)
    except Blocked as error:
        return blocked(str(error))
    except OSError:
        return blocked("worker-start-failed")


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise Blocked("invalid-cli-arguments")


def main():
    def private_failure(exc_type, exc_value, traceback):
        print(json.dumps(blocked("worker-failed-or-resource-limit")))

    # Unexpected parser/runtime failures must not print attacker-controlled
    # exception strings or stack traces, including when --worker is invoked.
    sys.excepthook = private_failure
    if sys.argv[1:] == ["--worker"]:
        result = worker()
    else:
        parser = SafeArgumentParser(description=__doc__)
        parser.add_argument("--approve-inspection", action="store_true")
        parser.add_argument("--file")
        parser.add_argument("--sha256")
        parser.add_argument("--pages", help="Explicit 1-based pages, e.g. 1,3; no ranges")
        parser.add_argument("--whole-document", action="store_true",
                            help="Approve whole bounded non-PDF document, not rendered pages")
        parser.add_argument("--format", choices=sorted(FORMATS), default="auto")
        try:
            args = parser.parse_args()
            if not args.approve_inspection:
                raise Blocked("inspection-not-approved")
            pages = None if args.pages is None else [int(value) for value in args.pages.split(",")]
            result = assess({"approved": True, "path": args.file,
                             "sha256": args.sha256, "pages": pages,
                             "whole_document": args.whole_document, "format": args.format})
        except Blocked as error:
            result = blocked(str(error))
        except ValueError:
            result = blocked("invalid-page-selection")
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=True))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
