"""Private, versioned evidence for generated indexers; no service operations."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

try:
    from ._common import HelperFailure, digest
except ImportError:
    from _common import HelperFailure, digest


PROJECTION_FIELDS = {"non_schedule_digest", "schedule_digest", "schedule_raw_digest"}
TICKS = 10_000_000
DURATION = re.compile(r"P(?:(?P<days>[0-9]{1,9})D)?(?:T(?:(?P<hours>[0-9]{1,9})H)?"
                      r"(?:(?P<minutes>[0-9]{1,9})M)?(?:(?P<seconds>[0-9]{1,9})(?:\.(?P<fraction>[0-9]{1,7}))?S)?)?")
INSTANT = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})"
                     r"(?:\.([0-9]{1,7}))?(Z|[+-][0-9]{2}:[0-9]{2})")


def note(diagnostics, severity, code, field, message, request_id):
    entry = dict(severity=severity, code=code, field=field, message=message, request_id=request_id)
    if entry not in diagnostics:
        diagnostics.append(entry)


def failure(diagnostics, code, field, message, request_id):
    note(diagnostics, "error", code, field, message, request_id)
    return HelperFailure(code, message, blocked_at="indexer-verification", request_id=request_id)


def interval(value):
    match = DURATION.fullmatch(value) if isinstance(value, str) and len(value) <= 96 else None
    if not match or not any(match.group(k) for k in ("days", "hours", "minutes", "seconds")):
        raise ValueError("Unsupported duration")
    if "T" in value and not any(match.group(k) for k in ("hours", "minutes", "seconds")):
        raise ValueError("Empty time component")
    parts = match.groupdict()
    seconds = sum(int(parts[k] or 0) * scale for k, scale in
                  (("days", 86400), ("hours", 3600), ("minutes", 60), ("seconds", 1)))
    ticks = seconds * TICKS + int((parts["fraction"] or "").ljust(7, "0"))
    if not 300 * TICKS <= ticks <= 86400 * TICKS:
        raise ValueError("Indexer interval outside documented bounds")
    return ticks


def instant(value):
    match = INSTANT.fullmatch(value) if isinstance(value, str) and len(value) <= 40 else None
    if not match or match[8] == "-00:00":
        raise ValueError("Unknown or unsupported timezone")
    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    zone = match[8]
    offset = 0
    if zone != "Z":
        hours, minutes = int(zone[1:3]), int(zone[4:6])
        if hours > 14 or minutes > 59 or hours == 14 and minutes:
            raise ValueError("Invalid offset")
        offset = (hours * 60 + minutes) * (-1 if zone[0] == "-" else 1)
    stamp = datetime(year, month, day, hour, minute, second,
                     tzinfo=timezone(timedelta(minutes=offset))).astimezone(timezone.utc)
    elapsed = stamp - datetime(1, 1, 1, tzinfo=timezone.utc)
    return (elapsed.days * 86400 + elapsed.seconds) * TICKS + int((match[7] or "").ljust(7, "0"))


def schedule(value, *, present=True, diagnostics=None, request_id=None):
    diagnostics = diagnostics if diagnostics is not None else []
    if value is None:
        return {"state": "null" if present else "missing"}
    field = "schedule"
    try:
        if not isinstance(value, dict) or set(value) - {"interval", "startTime"}:
            raise ValueError("Unknown shape")
        field = "schedule.interval"
        period = interval(value.get("interval"))
        field = "schedule.startTime"
        start = instant(value["startTime"]) if value.get("startTime") is not None else None
        return {"state": "object", "interval": period, "startTime": start}
    except (ValueError, OverflowError) as exc:
        raise failure(diagnostics, "indexer-schedule-evidence-invalid", field,
                      f"Generated indexer {field} is malformed or unsupported; no default is inferred.",
                      request_id) from exc


def observe(child, approved, diagnostics, request_id):
    observed = schedule(child.get("schedule"), present="schedule" in child,
                        diagnostics=diagnostics, request_id=request_id)
    expected = schedule(approved, diagnostics=diagnostics, request_id=request_id)
    if approved is not None:
        for field in ("interval", "startTime"):
            if field == "startTime" and approved.get(field) is None:
                continue
            if observed.get(field) != expected[field]:
                raise failure(diagnostics, "indexer-schedule-constraint-violation", f"schedule.{field}",
                              f"Generated indexer schedule.{field} violates the approved constraint; this is not an ingestion failure.",
                              request_id)
            if child["schedule"].get(field) != approved.get(field):
                note(diagnostics, "info", "indexer-schedule-format-equivalent", f"schedule.{field}",
                     "Schedule formats represent the same duration or instant.", request_id)
    if observed != expected:
        note(diagnostics, "warning", "indexer-schedule-unconstrained", "schedule",
             "Generated schedule differs on unconstrained timing; recurring work/cost is possible. No schedule was changed or default assumed.",
             request_id)
    return {
        "etag": child["@odata.etag"], "digest": digest(child),
        "non_schedule_digest": digest({k: v for k, v in child.items() if k not in {"schedule", "@odata.etag"}}),
        "schedule_digest": digest(observed),
        "schedule_raw_digest": digest({"present": "schedule" in child, "value": child.get("schedule")}),
    }


def compare(current, expected, diagnostics, request_id):
    if current == expected:
        return
    if not PROJECTION_FIELDS <= set(expected):
        raise failure(diagnostics, "indexer-legacy-evidence-insufficient", "indexer",
                      "Legacy full-hash evidence differs; no schedule preimage/projection exists. Retain it; do not auto-upgrade.",
                      request_id)
    if current["digest"] == expected["digest"]:
        raise failure(diagnostics, "indexer-evidence-inconsistent", "indexer",
                      "Equal full hashes have inconsistent version/projection evidence.", request_id)
    if current["non_schedule_digest"] != expected["non_schedule_digest"]:
        raise failure(diagnostics, "indexer-definition-drift", "indexer",
                      "A non-schedule indexer field changed; schedule policy cannot admit it.", request_id)
    if current["schedule_raw_digest"] == expected["schedule_raw_digest"]:
        raise failure(diagnostics, "indexer-version-unexplained", "@odata.etag",
                      "Indexer version/full hash changed without an observed schedule change; the revision is unproven.", request_id)
    equivalent = current["schedule_digest"] == expected["schedule_digest"]
    note(diagnostics, "info" if equivalent else "warning",
         "indexer-schedule-format-equivalent" if equivalent else "indexer-schedule-unconstrained",
         "schedule", "Only schedule changed; every other observed field matches the retained projection and approved timing constraints hold.",
         request_id)


def warnings(diagnostics):
    return list(dict.fromkeys(item["message"] for item in diagnostics if item["severity"] == "warning"))
