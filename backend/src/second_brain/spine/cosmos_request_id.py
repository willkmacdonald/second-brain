"""Helper for propagating capture_trace_id as Cosmos client_request_id.

Azure Cosmos SDK accepts `initial_headers` in request_options to forward
custom headers; this is the documented mechanism for client_request_id.
"""

from __future__ import annotations

from typing import Any


def apply_request_id(request_kwargs: dict[str, Any], request_id: str | None) -> None:
    """Mutate request_kwargs to include the x-ms-client-request-id header.

    No-op when request_id is None — never adds an empty header.
    """
    if not request_id:
        return
    headers = request_kwargs.setdefault("initial_headers", {})
    headers["x-ms-client-request-id"] = request_id


def trace_headers(request_id: str | None) -> dict[str, Any]:
    """Return kwargs dict with initial_headers for Cosmos calls.

    Returns empty dict when request_id is falsy — safe to unpack as
    ``await container.create_item(body=doc, **trace_headers(tid))``.
    """
    if not request_id:
        return {}
    return {
        "initial_headers": {"x-ms-client-request-id": request_id},
    }
