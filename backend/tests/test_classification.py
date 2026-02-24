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

    # Verify return string format: "Filed -> Bucket (conf) | {uuid}"
    assert result.startswith("Filed \u2192 Projects (0.85) | ")
    # Verify UUID suffix is a valid UUID
    import uuid as _uuid
    _uuid.UUID(result.split(" | ")[-1])

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
    """Low confidence classification creates records with status='pending'.

    Low-confidence items are silently filed as pending for later user review
    in the inbox. No HITL interruption on the capture screen.
    """
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "People")

    tools = _make_tools(mock_cosmos_manager, threshold=0.6)
    result = await tools.classify_and_file(
        bucket="People",
        confidence=0.45,
        **_BASE_KWARGS,
    )

    # Still filed but with "(needs review)" indicator and UUID suffix
    assert result.startswith("Filed (needs review) \u2192 People (0.45) | ")
    assert "(needs review)" in result
    # Verify UUID suffix
    import uuid as _uuid
    _uuid.UUID(result.split(" | ")[-1])

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    assert inbox_body["status"] == "pending"

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


async def test_classify_and_file_confidence_clamping_high(
    mock_cosmos_manager: object,
) -> None:
    """Confidence > 1.0 is clamped to 1.0."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.classify_and_file(
        bucket="Projects",
        confidence=1.5,
        raw_text="Test clamping",
        title="Clamp Test",
        people_score=0.1,
        projects_score=0.8,
        ideas_score=0.05,
        admin_score=0.05,
    )

    assert "(1.00)" in result

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    assert inbox_body["classificationMeta"]["confidence"] == 1.0


async def test_classify_and_file_confidence_clamping_negative(
    mock_cosmos_manager: object,
) -> None:
    """Confidence < 0.0 is clamped to 0.0 then defaulted to 0.75 (valid bucket fallback)."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.classify_and_file(
        bucket="Projects",
        confidence=-0.1,
        raw_text="Test clamping",
        title="Clamp Test",
        people_score=0.1,
        projects_score=0.8,
        ideas_score=0.05,
        admin_score=0.05,
    )

    # After clamping -0.1 -> 0.0, the 0.0 fallback logic applies: default to 0.75
    assert "(0.75)" in result

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    assert inbox_body["classificationMeta"]["confidence"] == 0.75


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
# Tests: request_misunderstood
# ---------------------------------------------------------------------------


async def test_request_misunderstood_creates_misunderstood_inbox(
    mock_cosmos_manager: object,
) -> None:
    """request_misunderstood creates an Inbox doc with status='misunderstood'."""
    _setup_echo(mock_cosmos_manager, "Inbox")

    tools = _make_tools(mock_cosmos_manager)
    await tools.request_misunderstood(
        raw_text="Aardvark",
        question_text="I'm not quite sure what you meant by 'Aardvark'. Could you tell me more?",
    )

    # Verify Inbox write
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    assert inbox_container.create_item.call_count == 1
    inbox_body = inbox_container.create_item.call_args[1]["body"]
    assert inbox_body["status"] == "misunderstood"
    assert inbox_body["filedRecordId"] is None
    assert inbox_body["classificationMeta"] is None
    assert inbox_body["title"] is None
    assert inbox_body["clarificationText"] == (
        "I'm not quite sure what you meant by 'Aardvark'. Could you tell me more?"
    )
    assert inbox_body["rawText"] == "Aardvark"

    # No bucket container writes
    for name in ("People", "Projects", "Ideas", "Admin"):
        container = mock_cosmos_manager.get_container(name)
        container.create_item.assert_not_called()


async def test_request_misunderstood_returns_parseable_string(
    mock_cosmos_manager: object,
) -> None:
    """Return string matches format 'Misunderstood -> {uuid} | {text}'."""
    import re
    import uuid

    _setup_echo(mock_cosmos_manager, "Inbox")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.request_misunderstood(
        raw_text="xyz",
        question_text="Could you tell me what 'xyz' refers to?",
    )

    # Parse the return string
    pattern = r"Misunderstood\s*\u2192\s*([a-f0-9\-]+)\s*\|\s*(.+)"
    match = re.match(pattern, result, re.DOTALL)
    assert match is not None, f"Return string did not match expected format: {result}"

    inbox_item_id = match.group(1)
    question_text = match.group(2)

    # Verify UUID format
    uuid.UUID(inbox_item_id)  # Raises if invalid

    # Verify question text is present
    assert "xyz" in question_text
