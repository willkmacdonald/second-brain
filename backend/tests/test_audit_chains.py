"""Tests for EXPECTED_CHAINS shape and ExpectedSegment dataclass."""

from __future__ import annotations

import pytest

from second_brain.spine.audit.chains import (
    EXPECTED_CHAINS,
    ExpectedSegment,
    get_expected_chain,
    required_segments,
)


def test_expected_segment_is_frozen_dataclass():
    seg = ExpectedSegment("backend_api", required=True)
    with pytest.raises(AttributeError):  # FrozenInstanceError is a subclass
        seg.required = False  # type: ignore[misc]


def test_all_four_kinds_have_chains():
    assert set(EXPECTED_CHAINS) == {"capture", "thread", "request", "crud"}


def test_capture_chain_required_segments():
    chain = EXPECTED_CHAINS["capture"]
    required = [s.segment_id for s in chain if s.required]
    assert required == ["mobile_capture", "backend_api", "classifier"]


def test_capture_chain_optional_segments():
    chain = EXPECTED_CHAINS["capture"]
    optional = [s.segment_id for s in chain if not s.required]
    assert set(optional) == {"admin", "external_services", "cosmos"}


def test_thread_chain():
    chain = EXPECTED_CHAINS["thread"]
    assert [s.segment_id for s in chain if s.required] == [
        "investigation",
        "backend_api",
    ]
    assert [s.segment_id for s in chain if not s.required] == ["cosmos"]


def test_request_chain_cosmos_required():
    """Per spec section 'Expected Segment Chains', cosmos required for request."""
    chain = EXPECTED_CHAINS["request"]
    assert [s.segment_id for s in chain if s.required] == [
        "backend_api",
        "cosmos",
    ]


def test_crud_chain_cosmos_required():
    """Per spec section 'Expected Segment Chains', cosmos required for crud."""
    chain = EXPECTED_CHAINS["crud"]
    required = [s.segment_id for s in chain if s.required]
    assert required == ["mobile_ui", "backend_api", "cosmos"]


def test_get_expected_chain_returns_chain():
    assert get_expected_chain("capture") == EXPECTED_CHAINS["capture"]


def test_required_segments_helper():
    assert required_segments("crud") == ["mobile_ui", "backend_api", "cosmos"]
