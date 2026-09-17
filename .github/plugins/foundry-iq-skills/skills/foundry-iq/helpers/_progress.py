"""Bounded, content-free observations; never a service execution controller."""
from __future__ import annotations

from functools import wraps
from contextlib import contextmanager
import copy
from datetime import datetime
import json
import math
import os
import sys
import time
import threading

try:
    from ._common import HelperFailure
except ImportError:
    from _common import HelperFailure


STAGES = {
    "file-source": ("validation", "source-reconciliation", "file-inventory", "file-upload", "file-readback"),
    "file-upload": ("file-inventory", "file-upload", "file-readback"),
    "blob-source": ("validation", "blob-inventory", "source-reconciliation", "ingestion-cycle",
                    "blob-readback", "source-readback"),
    "blob-monitor": ("ingestion-cycle",),
    "blob-capture": ("evidence-validation", "context-check", "source-binding", "blob-inventory", "checkpoint"),
    "blob-recheck": ("evidence-validation", "context-check", "source-binding", "blob-inventory",
                     "ingestion-cycle", "blob-readback", "source-readback", "context-readback"),
    "search-bootstrap": ("validation", "context-check", "region-check", "absence-check", "search-submit",
                         "arm-wait", "arm-readback"),
}
COUNTS = frozenset(("uploads_acknowledged", "files_reused", "files_verified",
                    "status_checks", "cycle_updates_processed", "cycle_items_skipped",
                    "files_failed", "files_unverified", "files_not_attempted", "files_pending", "files_ingested"))
FILE_HEARTBEAT_SECONDS = 5
IO_WARNING = "progress-output-failed: stderr progress could not be written; execution result is authoritative."
SHUTDOWN_WARNING = "progress-shutdown-flush-unresolved: failed stderr could not be redirected; shutdown may override the exit code."


def validate_blob_progress(value):
    fields = {"schema_version", "phase", "run_start", "processed", "failed", "skipped",
              "unit", "total", "remaining", "denominator", "synchronization_status",
              "elapsed_seconds", "next_check_seconds"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("Invalid Blob progress shape.")
    if (value["schema_version"] != "1.0" or value["unit"] != "item-updates"
            or value["denominator"] != "not-comparable-to-files"
            or value["total"] is not None or value["remaining"] is not None
            or value["phase"] not in ("ingesting", "waiting", "throttled", "paused", "completed", "failed")
            or value["synchronization_status"] not in ("not-reported", "active", "creating", "deleting")):
        raise ValueError("Invalid Blob progress labels.")
    for field in ("processed", "failed", "skipped"):
        count = value[field]
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("Invalid Blob progress count.")
    for field in ("elapsed_seconds", "next_check_seconds"):
        number = value[field]
        if field == "next_check_seconds" and number is None:
            continue
        if type(number) not in (int, float) or not math.isfinite(number) or number < 0:
            raise ValueError("Invalid Blob progress timing.")
    if value["next_check_seconds"] is not None and value["next_check_seconds"] > 60:
        raise ValueError("Invalid Blob progress wait.")
    start = value["run_start"]
    if start is not None:
        if not isinstance(start, str) or len(start) > 40:
            raise ValueError("Invalid Blob progress run.")
        parsed = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.isoformat() != start:
            raise ValueError("Blob progress run must be a canonical timestamp.")


class Progress:
    def __init__(self, workflow, *, enabled=True, stream=None, clock=time.monotonic):
        self.stages = STAGES[workflow]
        self.workflow = workflow
        self.enabled = enabled
        self.stream = stream
        self.clock = clock
        self.depth = 0
        self.stage = self.stages[0]
        self.counts = {}
        self.started = None
        self.elapsed = 0.0
        self.last_sent = None
        self.last_stage = None
        self.output_failed = False
        self.shutdown_flush_unresolved = False
        self.blob_progress = None
        self.last_blob_phase = None

    def blob_update(self, value):
        if not self.workflow.startswith("blob-"):
            raise ValueError("Blob progress cannot describe a File or ARM workflow.")
        validate_blob_progress(value)
        self.blob_progress = copy.deepcopy(value)
        for field, target in (("processed", "cycle_updates_processed"), ("skipped", "cycle_items_skipped")):
            self.counts.pop(target, None)
            if value[field] is not None:
                self.counts[target] = value[field]
        self.update("ingestion-cycle")

    def update(self, stage, **counts):
        if stage not in self.stages or self.stages.index(stage) < self.stages.index(self.stage):
            raise ValueError("Invalid progress stage transition.")
        if any(key not in COUNTS or type(value) is not int or value < 0 for key, value in counts.items()):
            raise ValueError("Invalid progress count.")
        self.stage = stage
        self.counts.update(counts)
        self._emit("running")

    def waiting(self, seconds):
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 <= seconds <= 30:
            raise ValueError("Invalid recovery wait.")
        self._emit("waiting", wait={"reason": "http-429", "seconds": seconds})

    @contextmanager
    def processing_file(self, ordinal, total, attempt):
        if (self.workflow not in {"file-source", "file-upload"} or type(ordinal) is not int
                or type(total) is not int or not 1 <= ordinal <= total <= 200 or attempt not in (1, 2)):
            raise ValueError("Invalid active file.")
        active = {"ordinal": ordinal, "total": total, "attempt": attempt}
        if not self.enabled or self.output_failed:
            yield
            return
        started = self.clock()
        stop = threading.Event()

        def pulse():
            while not stop.wait(FILE_HEARTBEAT_SECONDS):
                if self.output_failed:
                    return
                self._emit("processing", active=active, active_started=started)

        self._emit("processing", active=active, active_started=started)
        worker = threading.Thread(target=pulse, name="foundry-file-progress", daemon=True)
        worker.start()
        try:
            yield
        finally:
            stop.set()
            worker.join()

    def _emit(self, state, *, wait=None, active=None, active_started=None):
        if not self.enabled or self.output_failed:
            return
        observed = self.clock()
        # Clock regressions/nonfinite observations must not create negative time
        # or bypass throttling. Progress never shares the service deadline clock.
        if math.isfinite(observed):
            if self.started is None:
                self.started = observed
            delta = observed - self.started
            if math.isfinite(delta):
                self.elapsed = max(self.elapsed, delta)
        phase = self.blob_progress["phase"] if self.blob_progress is not None else None
        if (state == "running" and self.stage == self.last_stage and phase == self.last_blob_phase
                and self.last_sent is not None and self.elapsed - self.last_sent < 1.0):
            return
        event = {
            "event": "progress", "workflow": self.workflow, "activity": self.stage,
            "state": state, "elapsed_seconds": round(self.elapsed, 3),
            "remaining_checks": [] if state == "completed" else list(self.stages[self.stages.index(self.stage) + 1:]),
        }
        if self.counts:
            event["completed_counts"] = dict(self.counts)
        if wait is not None:
            event["wait"] = wait
        if active is not None:
            duration = observed - active_started
            event["processing_file"] = {**active, "elapsed_seconds": round(max(0, duration), 3) if math.isfinite(duration) else 0}
        if self.blob_progress is not None:
            value = self.blob_progress
            event["blob_progress"] = copy.deepcopy(value)
            counts = "; ".join(f"{field}={value[field] if value[field] is not None else 'unknown'}"
                               for field in ("processed", "failed", "skipped"))
            next_check = ("paused/resumable" if value["phase"] == "paused" else "none") if value["next_check_seconds"] is None else f"{value['next_check_seconds']:g}s"
            event["message"] = (
                f"Blob ingestion observation {value['phase']}: item updates {counts}; file total/remaining unknown "
                f"(not comparable); elapsed={value['elapsed_seconds']:g}s; next check={next_check}."
            )
        stream = self.stream if self.stream is not None else sys.stderr
        try:
            text = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            if stream.write(text) != len(text):
                raise OSError("Short progress write.")
            stream.flush()
        except (OSError, UnicodeError, ValueError):
            # Continue the approved operation, retaining a fixed secondary warning
            # even when stderr itself is broken. Never replace a primary failure.
            self.output_failed = True
            self._disable_failed_default_stderr(stream)
        self.last_sent, self.last_stage = self.elapsed, self.stage
        self.last_blob_phase = phase

    def _disable_failed_default_stderr(self, stream):
        if self.stream is not None or stream is not sys.__stderr__ or stream.closed:
            return
        try:
            if stream.fileno() == 2:
                # A failed TextIOWrapper flush can retain pending bytes. Redirect
                # only the failed native stderr so shutdown can drain that buffer
                # without replacing the authoritative process exit status.
                sink = os.open(os.devnull, os.O_WRONLY)
                try:
                    os.dup2(sink, 2)
                finally:
                    if sink != 2:
                        os.close(sink)
        except (OSError, ValueError):
            self.shutdown_flush_unresolved = True

    def finish(self, result=None, failure=None):
        if self.blob_progress is not None and failure is not None:
            self.blob_progress.update(phase="failed", next_check_seconds=None)
        if failure is not None:
            state = "partial" if failure.partial or failure.writes else "blocked"
        else:
            state = {"verified": "completed", "unverified": "blocked"}.get(result["status"], result["status"])
        if state not in {"completed", "blocked", "partial"}:
            raise ValueError("Invalid progress terminal state.")
        self._emit(state)
        if self.output_failed:
            warnings = failure.warnings if failure is not None else result.setdefault("warnings", [])
            if IO_WARNING not in warnings:
                warnings.append(IO_WARNING)
            if self.shutdown_flush_unresolved and SHUTDOWN_WARNING not in warnings:
                warnings.append(SHUTDOWN_WARNING)


def reporting(workflow):
    """One reporter and terminal event across nested public entrypoints."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, progress=None, **kwargs):
            if progress is None:
                progress = Progress(workflow, enabled=False)
            outer = progress.depth == 0
            progress.depth += 1
            try:
                result = function(*args, progress=progress, **kwargs)
            except HelperFailure as failure:
                if outer:
                    progress.finish(failure=failure)
                raise
            else:
                if outer:
                    progress.finish(result=result)
                return result
            finally:
                progress.depth -= 1
        return wrapped
    return decorate


def add_progress_argument(parser):
    parser.add_argument("--no-progress", dest="progress", action="store_false",
                        help="Suppress content-free execution progress on stderr.")
