"""Readback guard shared by source creation and retained-source verification."""
from __future__ import annotations

from typing import Any

try:
    from ._common import HelperFailure, Transport
    from . import _embedding, _search_read
except ImportError:
    from _common import HelperFailure, Transport
    import _embedding
    import _search_read


def guard_readback_transport(plan: dict[str, Any], transport: Transport) -> Transport:
    if "embedding" not in plan and "content_understanding" not in plan:
        return transport
    url = _search_read.resource_url(plan["source"])

    def guarded(method: str, target: str, token: str, **kwargs: Any):
        response = transport(method, target, token, **kwargs)
        if method == "GET" and target == url and response.status == 200:
            try:
                _embedding.verify_source_readback(plan.get("embedding"), response.body)
                if "content_understanding" in plan:
                    try:
                        from . import _blob_source_read as blob_source, _file_source_config as file_source
                    except ImportError:
                        import _blob_source_read as blob_source, _file_source_config as file_source
                    owner = file_source if plan["source"]["desired"]["kind"] == "file" else blob_source
                    owner.verify_content_understanding_readback(plan["content_understanding"], response.body)
            except HelperFailure as failure:
                failure.request_id = response.request_id
                raise
        return response

    return guarded
