"""Verify apply_request_id flows as x-ms-client-request-id on Cosmos kwargs."""

from second_brain.spine.cosmos_request_id import apply_request_id


def test_apply_request_id_sets_initial_headers() -> None:
    kwargs: dict = {}
    apply_request_id(kwargs, "trace-1")
    assert kwargs["initial_headers"]["x-ms-client-request-id"] == "trace-1"


def test_apply_request_id_no_op_when_none() -> None:
    kwargs: dict = {}
    apply_request_id(kwargs, None)
    assert "initial_headers" not in kwargs


def test_apply_request_id_preserves_existing_headers() -> None:
    kwargs: dict = {"initial_headers": {"x-custom": "foo"}}
    apply_request_id(kwargs, "trace-2")
    assert kwargs["initial_headers"]["x-ms-client-request-id"] == "trace-2"
    assert kwargs["initial_headers"]["x-custom"] == "foo"


def test_trace_headers_returns_kwargs_with_header() -> None:
    from second_brain.spine.cosmos_request_id import trace_headers

    result = trace_headers("trace-3")
    assert result["initial_headers"]["x-ms-client-request-id"] == "trace-3"


def test_trace_headers_returns_empty_when_none() -> None:
    from second_brain.spine.cosmos_request_id import trace_headers

    assert trace_headers(None) == {}
    assert trace_headers("") == {}
