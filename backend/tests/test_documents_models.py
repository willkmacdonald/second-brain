"""Pydantic model tests for ErrandItem + TaskItem backlink fields (Phase 25 REQ-BL-01).

Tests prove:
- New optional sourceInboxItemId + sourceCaptureTraceId fields default to None
- Both models accept the fields when provided as strings
- Pre-Phase-25 raw dicts (no backlink keys) deserialize cleanly via model_validate
"""

from second_brain.models.documents import ErrandItem, TaskItem


def test_errand_item_optional_backlinks_default_none() -> None:
    """ErrandItem without backlinks parses cleanly and defaults both to None."""
    doc = ErrandItem(destination="jewel", name="milk")
    assert doc.sourceInboxItemId is None
    assert doc.sourceCaptureTraceId is None


def test_errand_item_optional_backlinks_accept_strings() -> None:
    """ErrandItem accepts both backlink fields as non-empty strings."""
    doc = ErrandItem(
        destination="jewel",
        name="milk",
        sourceInboxItemId="inbox-42",
        sourceCaptureTraceId="trace-99",
    )
    assert doc.sourceInboxItemId == "inbox-42"
    assert doc.sourceCaptureTraceId == "trace-99"


def test_errand_item_legacy_doc_compatibility() -> None:
    """Pre-Phase-25 raw dict (no backlink fields) deserializes via model_validate."""
    legacy = {
        "id": "legacy-1",
        "destination": "cvs",
        "name": "toothpaste",
        "needsRouting": False,
        "sourceName": None,
        "sourceUrl": None,
    }
    doc = ErrandItem.model_validate(legacy)
    assert doc.sourceInboxItemId is None
    assert doc.sourceCaptureTraceId is None


def test_task_item_optional_backlinks_default_none() -> None:
    """TaskItem without backlinks parses cleanly and defaults both to None."""
    doc = TaskItem(name="Book eye appointment")
    assert doc.sourceInboxItemId is None
    assert doc.sourceCaptureTraceId is None


def test_task_item_optional_backlinks_accept_strings() -> None:
    """TaskItem accepts both backlink fields as non-empty strings."""
    doc = TaskItem(
        name="Book eye appointment",
        sourceInboxItemId="inbox-7",
        sourceCaptureTraceId="trace-13",
    )
    assert doc.sourceInboxItemId == "inbox-7"
    assert doc.sourceCaptureTraceId == "trace-13"


def test_task_item_legacy_doc_compatibility() -> None:
    """Pre-Phase-25 raw dict (no backlink fields) deserializes via model_validate."""
    legacy = {
        "id": "legacy-task-1",
        "userId": "will",
        "name": "Call dentist",
        "createdAt": "2026-05-01T10:00:00Z",
    }
    doc = TaskItem.model_validate(legacy)
    assert doc.sourceInboxItemId is None
    assert doc.sourceCaptureTraceId is None
