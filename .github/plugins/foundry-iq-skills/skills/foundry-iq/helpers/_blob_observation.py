"""Credential-free semantic projections, separate from cleanup integrity."""
from __future__ import annotations

try:
    from ._common import HelperFailure, digest
    from . import _indexer_observation as indexer
except ImportError:
    from _common import HelperFailure, digest
    import _indexer_observation as indexer


FIELDS = frozenset(("name", "type", "container", "identity", "description",
                    "dataChangeDetectionPolicy", "dataDeletionDetectionPolicy", "encryptionKey",
                    "fields", "scoringProfiles", "defaultScoringProfile", "corsOptions",
                    "suggesters", "analyzers", "normalizers", "tokenizers", "tokenFilters",
                    "charFilters", "similarity", "semantic", "vectorSearch",
                    "skills", "cognitiveServices", "knowledgeStore", "indexProjections",
                    "dataSourceName", "targetIndexName", "skillsetName", "parameters",
                    "fieldMappings", "outputFieldMappings", "cache", "disabled"))
PROJECTION_FIELDS = {"core_digest", "field_digests"}


def observe(child, kind):
    excluded = {"@odata.etag"}
    if kind == "datasource":
        excluded.add("credentials")
    if kind == "indexer":
        excluded.add("schedule")
    core = {key: value for key, value in child.items() if key not in excluded}
    fields = {key: digest(value) for key, value in core.items() if key in FIELDS}
    fields["additionalProperties"] = digest({key: value for key, value in core.items() if key not in FIELDS})
    result = {"core_digest": digest(core), "field_digests": fields}
    if kind == "datasource":
        result["credential_digest"] = digest({"present": "credentials" in child, "value": child.get("credentials")})
    return result


def note(diagnostics, kind, severity, code, field, request_id):
    indexer.note(diagnostics, severity, code, f"{kind}.{field}",
                 f"{kind}.{field}: {code}; values withheld.", request_id)


def compare(current, expected, kind, diagnostics, request_id):
    if current["digest"] == expected["digest"] and current != expected:
        raise HelperFailure(f"{kind}-evidence-inconsistent", "Equal full hashes have inconsistent projection evidence.",
                            blocked_at="verification", request_id=request_id)
    if current["core_digest"] != expected["core_digest"]:
        fields = current["field_digests"].keys() | expected["field_digests"].keys()
        for field in sorted(fields):
            if current["field_digests"].get(field) != expected["field_digests"].get(field):
                note(diagnostics, kind, "error", "definition-drift", field, request_id)
        raise HelperFailure("indexer-definition-drift" if kind == "indexer" else "definition-drift",
                            "Meaningful generated configuration changed; inspect child diagnostics.",
                            blocked_at="verification", request_id=request_id)
    if current["etag"] != expected["etag"]:
        note(diagnostics, kind, "info", "generated-version-changed", "@odata.etag", request_id)
    if kind == "datasource" and current["credential_digest"] != expected["credential_digest"]:
        note(diagnostics, kind, "warning", "datasource-credential-projection-changed", "credentials", request_id)


def indexer_only(diagnostics):
    return [item for item in diagnostics
            if not item["field"].startswith(("datasource.", "indexer.", "skillset.", "index."))]


def valid(value, kind, sha256):
    fields = {"etag", "digest"} | PROJECTION_FIELDS
    if kind == "indexer":
        fields |= indexer.PROJECTION_FIELDS
    if kind == "datasource":
        fields |= {"credential_digest", "binding_proof"}
    if not isinstance(value, dict) or set(value) != fields:
        return False
    hashes = fields - {"etag", "field_digests", "binding_proof"}
    return (isinstance(value["etag"], str) and bool(value["etag"].strip())
            and all(isinstance(value[key], str) and sha256.fullmatch(value[key]) for key in hashes)
            and isinstance(value["field_digests"], dict)
            and set(value["field_digests"]) <= FIELDS | {"additionalProperties"}
            and "additionalProperties" in value["field_digests"]
            and all(isinstance(item, str) and sha256.fullmatch(item)
                    for item in value["field_digests"].values())
            and (kind != "datasource" or isinstance(value["binding_proof"], str)
                 and value["binding_proof"] in {"resource-id", "unverified"}))
