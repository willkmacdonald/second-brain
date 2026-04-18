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
