"""Unit tests for ClassificationTools (classify_and_file + mark_as_junk).

Tests use the mock_cosmos_manager fixture from conftest.py. No real Azure calls.
"""

from unittest.mock import AsyncMock

import pytest

from second_brain.tools.classification import ClassificationTools

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tools(
    mock_cosmos_manager: object,
    threshold: float = 0.6,
) -> ClassificationTools:
    """Create a ClassificationTools instance with mock manager."""
    return ClassificationTools(mock_cosmos_manager, classification_threshold=threshold)


def _echo_body(*, body: dict) -> dict:
    """Side-effect for create_item: return the body it was called with."""
    return body


def _setup_echo(mock_cosmos_manager: object, container_name: str) -> None:
    """Set up a container's create_item to echo back the body."""
    container = mock_cosmos_manager.get_container(container_name)
    container.create_item = AsyncMock(side_effect=_echo_body)


def _get_body(mock_cosmos_manager: object, container: str) -> dict:
    """Extract the body dict from a container's create_item call."""
    c = mock_cosmos_manager.get_container(container)
    return c.create_item.call_args[1]["body"]


# Common call kwargs for classify_and_file
_BASE_KWARGS = {
    "raw_text": "Meet Sarah tomorrow at 3pm",
    "title": "Meeting with Sarah",
    "people_score": 0.85,
    "projects_score": 0.10,
    "ideas_score": 0.03,
    "admin_score": 0.02,
}


# ---------------------------------------------------------------------------
# Tests: classify_and_file
# ---------------------------------------------------------------------------


async def test_classify_and_file_high_confidence(mock_cosmos_manager: object) -> None:
    """High confidence: Inbox + bucket with status='classified'."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.classify_and_file(
        bucket="Projects",
        confidence=0.85,
        raw_text="Build the new dashboard",
        title="New Dashboard",
        people_score=0.05,
        projects_score=0.85,
        ideas_score=0.07,
        admin_score=0.03,
    )

    # Verify return string format
    assert result == "Filed \u2192 Projects (0.85)"

    # Verify Inbox write
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    assert inbox_container.create_item.call_count == 1
    inbox_body = inbox_container.create_item.call_args[1]["body"]
    assert inbox_body["rawText"] == "Build the new dashboard"
    assert inbox_body["status"] == "classified"
    assert inbox_body["classificationMeta"]["bucket"] == "Projects"
    assert inbox_body["classificationMeta"]["confidence"] == 0.85
    assert inbox_body["filedRecordId"] is not None

    # Verify Projects write
    projects_container = mock_cosmos_manager.get_container("Projects")
    assert projects_container.create_item.call_count == 1
    projects_body = projects_container.create_item.call_args[1]["body"]
    assert projects_body["rawText"] == "Build the new dashboard"
    assert projects_body["title"] == "New Dashboard"
    assert projects_body["inboxRecordId"] is not None


async def test_classify_and_file_low_confidence(mock_cosmos_manager: object) -> None:
    """Low confidence classification creates records with status='low_confidence'.

    Note: This tests the tool directly. In production the classifier agent would
    call request_clarification instead for < 0.6, but classify_and_file still
    works if called directly.
    """
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "People")

    tools = _make_tools(mock_cosmos_manager, threshold=0.6)
    result = await tools.classify_and_file(
        bucket="People",
        confidence=0.45,
        **_BASE_KWARGS,
    )

    # Still filed (per CONTEXT.md: "still file to best bucket")
    assert result == "Filed \u2192 People (0.45)"

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    assert inbox_body["status"] == "low_confidence"

    # Bucket document still written
    people_container = mock_cosmos_manager.get_container("People")
    assert people_container.create_item.call_count == 1


@pytest.mark.parametrize(
    "bucket,field_name",
    [
        ("People", "name"),
        ("Projects", "title"),
        ("Ideas", "title"),
        ("Admin", "title"),
    ],
)
async def test_classify_and_file_each_bucket(
    mock_cosmos_manager: object,
    bucket: str,
    field_name: str,
) -> None:
    """Each bucket receives the document with the correct field (name vs title)."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, bucket)

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.classify_and_file(
        bucket=bucket,
        confidence=0.80,
        **_BASE_KWARGS,
    )

    assert f"Filed \u2192 {bucket}" in result

    bucket_body = _get_body(mock_cosmos_manager, bucket)
    assert bucket_body[field_name] == "Meeting with Sarah"
    assert bucket_body["rawText"] == "Meet Sarah tomorrow at 3pm"


async def test_classify_and_file_invalid_bucket(mock_cosmos_manager: object) -> None:
    """Invalid bucket returns error string with no container writes."""
    tools = _make_tools(mock_cosmos_manager)
    result = await tools.classify_and_file(
        bucket="Unknown",
        confidence=0.90,
        **_BASE_KWARGS,
    )

    assert "Error" in result
    assert "Unknown" in result

    # No writes to any container
    for name in ("Inbox", "People", "Projects", "Ideas", "Admin"):
        container = mock_cosmos_manager.get_container(name)
        container.create_item.assert_not_called()


@pytest.mark.parametrize(
    "input_confidence,expected_clamped",
    [
        (1.5, 1.0),
        (-0.1, 0.0),
    ],
)
async def test_classify_and_file_confidence_clamping(
    mock_cosmos_manager: object,
    input_confidence: float,
    expected_clamped: float,
) -> None:
    """Confidence values outside 0.0-1.0 are clamped."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.classify_and_file(
        bucket="Projects",
        confidence=input_confidence,
        raw_text="Test clamping",
        title="Clamp Test",
        people_score=0.1,
        projects_score=0.8,
        ideas_score=0.05,
        admin_score=0.05,
    )

    assert f"({expected_clamped:.2f})" in result

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    assert inbox_body["classificationMeta"]["confidence"] == expected_clamped


async def test_classification_meta_fields(mock_cosmos_manager: object) -> None:
    """ClassificationMeta stored in document has all required fields."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    await tools.classify_and_file(
        bucket="Projects",
        confidence=0.75,
        raw_text="Build API",
        title="API Build",
        people_score=0.05,
        projects_score=0.75,
        ideas_score=0.15,
        admin_score=0.05,
    )

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    meta = inbox_body["classificationMeta"]

    # All required fields present
    assert meta["bucket"] == "Projects"
    assert meta["confidence"] == 0.75
    assert len(meta["allScores"]) == 4
    assert set(meta["allScores"].keys()) == {"People", "Projects", "Ideas", "Admin"}
    assert meta["classifiedBy"] == "Classifier"
    assert meta["agentChain"] == ["Orchestrator", "Classifier"]
    assert "classifiedAt" in meta


async def test_bidirectional_links(mock_cosmos_manager: object) -> None:
    """Inbox filedRecordId matches bucket doc id, and vice versa."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    await tools.classify_and_file(
        bucket="Projects",
        confidence=0.90,
        raw_text="Link test",
        title="Link Test",
        people_score=0.02,
        projects_score=0.90,
        ideas_score=0.05,
        admin_score=0.03,
    )

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    projects_body = _get_body(mock_cosmos_manager, "Projects")

    # Bi-directional link: inbox -> bucket and bucket -> inbox
    assert inbox_body["filedRecordId"] == projects_body["id"]
    assert projects_body["inboxRecordId"] == inbox_body["id"]


# ---------------------------------------------------------------------------
# Tests: mark_as_junk
# ---------------------------------------------------------------------------


async def test_mark_as_junk(mock_cosmos_manager: object) -> None:
    """Junk input creates Inbox-only record with status 'unclassified'."""
    _setup_echo(mock_cosmos_manager, "Inbox")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.mark_as_junk(raw_text="asdfghjkl")

    assert result == "Capture logged as unclassified"

    # Inbox write
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    assert inbox_container.create_item.call_count == 1
    inbox_body = inbox_container.create_item.call_args[1]["body"]
    assert inbox_body["rawText"] == "asdfghjkl"
    assert inbox_body["status"] == "unclassified"
    assert inbox_body["classificationMeta"] is None

    # No bucket writes
    for name in ("People", "Projects", "Ideas", "Admin"):
        container = mock_cosmos_manager.get_container(name)
        container.create_item.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: request_clarification
# ---------------------------------------------------------------------------

# Common call kwargs for request_clarification
_CLARIFICATION_KWARGS = {
    "raw_text": "Interesting conversation with Mike about moving to Austin",
    "title": "Mike Austin conversation",
    "top_bucket": "People",
    "top_confidence": 0.55,
    "second_bucket": "Ideas",
    "second_confidence": 0.42,
    "clarification_text": (
        "I'm torn between People (0.55) and Ideas (0.42). "
        "This mentions Mike (a person) but also discusses a potential "
        "relocation which could be a life change idea. Which fits better?"
    ),
    "people_score": 0.55,
    "projects_score": 0.01,
    "ideas_score": 0.42,
    "admin_score": 0.02,
}


async def test_request_clarification_creates_pending_inbox(
    mock_cosmos_manager: object,
) -> None:
    """request_clarification creates a pending Inbox doc with no bucket write."""
    _setup_echo(mock_cosmos_manager, "Inbox")

    tools = _make_tools(mock_cosmos_manager)
    await tools.request_clarification(**_CLARIFICATION_KWARGS)

    # Verify Inbox write
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    assert inbox_container.create_item.call_count == 1
    inbox_body = inbox_container.create_item.call_args[1]["body"]
    assert inbox_body["status"] == "pending"
    assert inbox_body["filedRecordId"] is None
    expected_text = _CLARIFICATION_KWARGS["clarification_text"]
    assert inbox_body["clarificationText"] == expected_text
    assert inbox_body["rawText"] == _CLARIFICATION_KWARGS["raw_text"]
    assert inbox_body["title"] == _CLARIFICATION_KWARGS["title"]
    assert inbox_body["classificationMeta"]["bucket"] == "People"
    assert inbox_body["classificationMeta"]["confidence"] == 0.55

    # No bucket container writes
    for name in ("People", "Projects", "Ideas", "Admin"):
        container = mock_cosmos_manager.get_container(name)
        container.create_item.assert_not_called()


async def test_request_clarification_returns_parseable_string(
    mock_cosmos_manager: object,
) -> None:
    """Return string matches format 'Clarification -> {uuid} | {text}'."""
    import re

    _setup_echo(mock_cosmos_manager, "Inbox")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.request_clarification(**_CLARIFICATION_KWARGS)

    # Parse the return string
    pattern = r"Clarification\s*\u2192\s*([a-f0-9\-]+)\s*\|\s*(.+)"
    match = re.match(pattern, result, re.DOTALL)
    assert match is not None, f"Return string did not match expected format: {result}"

    inbox_item_id = match.group(1)
    clarification_text = match.group(2)

    # Verify UUID format
    import uuid

    uuid.UUID(inbox_item_id)  # Raises if invalid

    # Verify clarification text is present
    assert "torn between" in clarification_text


async def test_request_clarification_invalid_bucket(
    mock_cosmos_manager: object,
) -> None:
    """Invalid bucket names return error string with no writes."""
    tools = _make_tools(mock_cosmos_manager)

    # Invalid top_bucket
    result = await tools.request_clarification(
        **{**_CLARIFICATION_KWARGS, "top_bucket": "Unknown"},
    )
    assert "Error" in result
    assert "Unknown" in result

    # Invalid second_bucket
    result = await tools.request_clarification(
        **{**_CLARIFICATION_KWARGS, "second_bucket": "BadBucket"},
    )
    assert "Error" in result
    assert "BadBucket" in result

    # No writes to any container
    for name in ("Inbox", "People", "Projects", "Ideas", "Admin"):
        container = mock_cosmos_manager.get_container(name)
        container.create_item.assert_not_called()
