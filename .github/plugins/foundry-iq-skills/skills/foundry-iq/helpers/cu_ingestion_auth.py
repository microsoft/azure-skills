"""Shared CU auth disclosure; private acquisition is restricted to File source PUTs."""
from __future__ import annotations

import base64
import copy
import json
import re

try:
    from . import _bootstrap_io
    from ._common import HelperFailure, HttpResult, MANAGEMENT_AUDIENCE, azure_cli_token, digest, require_allowed_fields
except ImportError:
    import _bootstrap_io
    from _common import HelperFailure, HttpResult, MANAGEMENT_AUDIENCE, azure_cli_token, digest, require_allowed_fields


API_VERSION = "2024-10-01"
PURPOSE = "file-standard-cu-source-put"
RESOURCE = re.compile(
    r"/subscriptions/([0-9a-fA-F-]{36})/resourceGroups/[A-Za-z0-9_.()-]{1,90}"
    r"/providers/Microsoft\.CognitiveServices/accounts/[A-Za-z0-9][A-Za-z0-9_.-]{1,63}",
    re.IGNORECASE,
)
ENDPOINT = re.compile(r"https://[a-z0-9][a-z0-9-]{0,62}\.services\.ai\.azure\.com/?")
UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


def approval_summary(adapter, auth, *, creating):
    modes = {
        "file": {"system-assigned", "api-key-arm", "api-key-environment"},
        "azureBlob": {"system-assigned"}, "adlsGen2": {"system-assigned"},
    }
    if adapter not in modes or auth not in modes[adapter]:
        raise failure("cu-adapter-auth-unsupported", "Select the supported adapter's verified CU auth contract; no cross-adapter auth fallback.")
    return {
        "adapter": adapter, "mode": auth,
        "contract": (
            "File system MI is implemented in inspected service code; live compatibility is unverified. Explicit legacy key modes remain supported, without fallback."
            if adapter == "file" else
            "Documented Search system-assigned CU identity; Cognitive Services User on the selected CU account. No key fallback."
        ),
        "credential_read": (
            "none: exact source reuse" if not creating else
            "private ARM listKeys/key1 for the exact source PUT only" if auth == "api-key-arm" else
            "explicit existing ENV only" if auth == "api-key-environment" else
            "none: managed identity"
        ),
        "setup": (
            "Reuse verified dependencies. Resolve only missing changes through packaged native bootstrap with exact identity/role/scope and explicit permission/local-auth approval; source execution does not alter them and unsupported updates block."
            if creating else "No CU setup or reingestion for exact source reuse."
        ),
        "consent": "Disclose auth and cost/data/access in the concrete source approval; no separate manual credential/MI/ENV confirmation. Material changes require refreshed approval.",
    }


def failure(code, message, *, status=None, partial=False):
    return HelperFailure(code, message, blocked_at="cu-authentication", status=status, partial=partial)


def token_principal(token):
    # This binds CLI token identity, not token validity; ARM validates the credential.
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if any(not isinstance(claims.get(k), str) or UUID.fullmatch(claims[k]) is None for k in ("tid", "oid")):
            raise ValueError()
        return claims["tid"], digest({"object_id": claims["oid"]})
    except Exception:
        raise failure("cu-context-unavailable", "The signed-in ARM token lacks a usable tenant/object identity binding; token details withheld.") from None


def account_context():
    """Read non-secret CLI identity metadata; never run a key-returning subprocess."""
    try:
        code, stdout, _ = _bootstrap_io.run_cli(["account", "show"], 30)
        value = json.loads(stdout) if code == 0 else None
        user = value.get("user") if isinstance(value, dict) else None
        if (
            not isinstance(user, dict) or user.get("type") not in ("user", "servicePrincipal")
            or not isinstance(user.get("name"), str) or not user["name"]
            or value.get("environmentName") != "AzureCloud" or value.get("state") != "Enabled"
        ):
            raise ValueError()
        tenant, principal = token_principal(azure_cli_token(MANAGEMENT_AUDIENCE))
        if tenant != value["tenantId"]:
            raise ValueError()
        context = {
            "subscription_id": value["id"], "tenant_id": value["tenantId"],
            "principal_digest": principal,
        }
        validate_context(context)
        return context
    except Exception:
        raise failure("cu-context-unavailable", "Use an existing signed-in AzureCloud CLI context; identity details withheld.") from None


def validate_context(context):
    if not isinstance(context, dict):
        raise failure("cu-context-invalid", "Retain the planner's exact signed-in context.")
    require_allowed_fields(context, {"subscription_id", "tenant_id", "principal_digest"}, label="File CU context")
    if (
        any(not isinstance(context.get(k), str) or UUID.fullmatch(context[k]) is None
            for k in ("subscription_id", "tenant_id"))
        or not isinstance(context.get("principal_digest"), str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", context["principal_digest"]) is None
    ):
        raise failure("cu-context-invalid", "Retain complete tenant, subscription and principal binding.")


def acquisition(choice, context):
    result = {
        "resource_id": choice["resource_id"], "endpoint": choice["endpoint"].rstrip("/"),
        "context": copy.deepcopy(context), "api_version": API_VERSION, "key_name": "key1", "purpose": PURPOSE,
    }
    validate_acquisition(result, choice["endpoint"])
    return result


def validate_acquisition(value, endpoint):
    if not isinstance(value, dict):
        raise failure("cu-acquisition-invalid", "Retain the exact approved File CU acquisition contract.")
    require_allowed_fields(value, {"resource_id", "endpoint", "context", "api_version", "key_name", "purpose"},
                           label="File CU acquisition")
    resource = RESOURCE.fullmatch(value.get("resource_id", "")) if isinstance(value.get("resource_id"), str) else None
    if (
        resource is None or not isinstance(value.get("endpoint"), str)
        or ENDPOINT.fullmatch(value["endpoint"]) is None
        or value["endpoint"] != endpoint.rstrip("/")
        or value.get("api_version") != API_VERSION or value.get("key_name") != "key1"
        or value.get("purpose") != PURPOSE
    ):
        raise failure("cu-acquisition-invalid", "Only the exact selected AIServices account, endpoint and key1 source-PUT purpose are supported.")
    validate_context(value.get("context"))
    if resource.group(1).casefold() != value["context"]["subscription_id"].casefold():
        raise failure("cu-subscription-mismatch", "Select the approved CU account's existing CLI subscription, then refresh the plan; no context switching was performed.")


def check_context(expected, provider):
    current = provider()
    validate_context(current)
    if current != expected:
        raise failure("cu-context-drift", "Signed-in tenant, subscription or principal changed; restore the approved context or refresh the plan and approval.")


class PrivateKey:
    def __init__(self, contract, *, token_provider, transport, context_provider, recheck):
        self.contract = contract
        self.token_provider = token_provider
        self.raw_transport = transport
        self.context_provider = context_provider
        self.recheck = recheck
        self._secrets = ()
        self._attempted = False

    def acquire(self):
        if self._attempted:
            raise failure("cu-acquisition-repeated", "Credential acquisition is single-attempt; no alternate key, account or auth channel was tried.")
        self._attempted = True
        expected = self.contract["context"]
        check_context(expected, self.context_provider)
        self.recheck()
        try:
            token = self.token_provider(MANAGEMENT_AUDIENCE)
            if token_principal(token) != (expected["tenant_id"], expected["principal_digest"]):
                raise failure("cu-context-drift", "ARM token identity differs from the approved caller.")
            check_context(expected, self.context_provider)
            result = self.raw_transport(
                "POST", f"{MANAGEMENT_AUDIENCE}{self.contract['resource_id']}/listKeys?api-version={API_VERSION}",
                token, follow_redirects=False, max_response_bytes=16384,
            )
        except HelperFailure as error:
            if error.code in ("cu-context-drift", "cu-context-unavailable"):
                raise failure(error.code, "Signed-in ARM identity no longer matches the usable approved context; refresh approval.") from None
            raise self._acquisition_failure(error.http_status) from None
        except Exception:
            raise self._acquisition_failure(None) from None
        if result.status != 200:
            raise self._acquisition_failure(result.status)
        body = result.body
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("key1"), str)
            or not 1 <= len(body["key1"]) <= 4096
            or not body["key1"].isascii() or any(c.isspace() or ord(c) < 33 for c in body["key1"])
            or (body.get("key2") is not None and (
                not isinstance(body["key2"], str) or len(body["key2"]) > 4096
            ))
        ):
            raise failure("cu-key-response-invalid", "ARM listKeys did not return a usable key1; no alternate key was selected.")
        self._secrets = tuple(v for k in ("key1", "key2") if isinstance(v := body.get(k), str) and v)
        check_context(expected, self.context_provider)
        return body["key1"]

    @staticmethod
    def _acquisition_failure(status):
        status = status if type(status) is int and 100 <= status <= 599 else None
        if status in (401, 403):
            return failure(
                "cu-key-access-denied",
                "The signed-in caller needs Microsoft.CognitiveServices/accounts/listKeys/action on the exact approved CU account. Have its owner resolve access under separate concrete approval; no roles or policies were changed.",
                status=status,
            )
        return failure("cu-key-acquisition-failed", "ARM listKeys failed for the approved CU account; details withheld and no retry or auth fallback performed.", status=status)

    def _redact(self, value):
        if isinstance(value, str):
            for secret in self._secrets:
                value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, dict):
            return {self._redact(k): self._redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact(v) for v in value]
        if isinstance(value, tuple):
            return tuple(self._redact(v) for v in value)
        return value

    def transport(self, method, url, token, **kwargs):
        if not self._secrets:
            return self.raw_transport(method, url, token, **kwargs)
        kwargs["follow_redirects"] = False
        try:
            result = self.raw_transport(method, url, token, **kwargs)
        except HelperFailure as error:
            raise HelperFailure(
                self._redact(error.code), "Azure request failed after private CU credential acquisition; response details withheld.",
                blocked_at=self._redact(error.blocked_at),
                status=error.http_status if type(error.http_status) is int and 100 <= error.http_status <= 599 else None,
                partial=error.partial, request_id=self._redact(error.request_id),
                writes=self._redact(error.writes), resources_remaining=self._redact(error.resources_remaining),
                resources_reused=self._redact(error.resources_reused), warnings=self._redact(error.warnings),
            ) from None
        except Exception:
            raise failure("cu-private-request-failed", "Azure request failed; private request/response details withheld.",
                          partial=method not in ("GET", "HEAD")) from None
        etags = self._redact(result.etag_values)
        versions = [
            *(result.etag_values or ()),
            *(value for name, value in result.headers.items() if name.lower() == "etag"),
            result.body.get("@odata.etag") if isinstance(result.body, dict) else None,
        ]
        if any(self._redact(value) != value for value in versions):
            # Redaction must not turn conflicting secret-bearing versions into equal evidence.
            etags = ("",)
        return HttpResult(result.status, self._redact(result.body), self._redact(result.headers), etags)
