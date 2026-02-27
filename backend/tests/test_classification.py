"""Unit tests for ClassifierTools (file_capture).

Tests use the mock_cosmos_manager fixture from conftest.py. No real Azure calls.
"""

from unittest.mock import AsyncMock

import pytest

from second_brain.tools.classification import ClassifierTools

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tools(
    mock_cosmos_manager: object,
    threshold: float = 0.6,
) -> ClassifierTools:
    """Create a ClassifierTools instance with mock manager."""
    return ClassifierTools(
        mock_cosmos_manager, classification_threshold=threshold
    )


def _echo_body(*, body: dict) -> dict:
    """Side-effect for create_item: return the body it was called with."""
    return body


def _setup_echo(
    mock_cosmos_manager: object, container_name: str
) -> None:
    """Set up a container's create_item to echo back the body."""
    container = mock_cosmos_manager.get_container(container_name)
    container.create_item = AsyncMock(side_effect=_echo_body)


def _get_body(mock_cosmos_manager: object, container: str) -> dict:
    """Extract the body dict from a container's create_item call."""
    c = mock_cosmos_manager.get_container(container)
    return c.create_item.call_args[1]["body"]


# ---------------------------------------------------------------------------
# Tests: file_capture -- classified
# ---------------------------------------------------------------------------


async def test_file_capture_classified(
    mock_cosmos_manager: object,
) -> None:
    """High confidence: Inbox + bucket with status='classified'."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.file_capture(
        text="Build the new dashboard",
        bucket="Projects",
        confidence=0.85,
        status="classified",
        title="New Dashboard",
    )

    # Verify return is a dict with expected keys
    assert isinstance(result, dict)
    assert result["bucket"] == "Projects"
    assert result["confidence"] == 0.85
    assert "item_id" in result

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


# ---------------------------------------------------------------------------
# Tests: file_capture -- pending
# ---------------------------------------------------------------------------


async def test_file_capture_pending(
    mock_cosmos_manager: object,
) -> None:
    """Low confidence: files with status='pending', still writes bucket."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "People")

    tools = _make_tools(mock_cosmos_manager, threshold=0.6)
    result = await tools.file_capture(
        text="Meet Sarah tomorrow at 3pm",
        bucket="People",
        confidence=0.45,
        status="pending",
        title="Meeting with Sarah",
    )

    # Verify return dict
    assert isinstance(result, dict)
    assert result["bucket"] == "People"
    assert result["confidence"] == 0.45

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    assert inbox_body["status"] == "pending"

    # Bucket document still written for pending status
    people_container = mock_cosmos_manager.get_container("People")
    assert people_container.create_item.call_count == 1


# ---------------------------------------------------------------------------
# Tests: file_capture -- misunderstood
# ---------------------------------------------------------------------------


async def test_file_capture_misunderstood(
    mock_cosmos_manager: object,
) -> None:
    """Misunderstood: Inbox only, no classificationMeta, no bucket write."""
    _setup_echo(mock_cosmos_manager, "Inbox")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.file_capture(
        text="Xyzzy",
        bucket="Admin",
        confidence=0.0,
        status="misunderstood",
        title="Untitled",
    )

    # file_capture returns dict on success even for misunderstood
    assert isinstance(result, dict)
    assert "item_id" in result

    # Verify Inbox write
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    assert inbox_container.create_item.call_count == 1
    inbox_body = inbox_container.create_item.call_args[1]["body"]
    assert inbox_body["status"] == "misunderstood"
    assert inbox_body["classificationMeta"] is None
    assert inbox_body["filedRecordId"] is None

    # No bucket container writes for misunderstood
    for name in ("People", "Projects", "Ideas", "Admin"):
        container = mock_cosmos_manager.get_container(name)
        container.create_item.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: file_capture -- each bucket
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bucket,field_name",
    [
        ("People", "name"),
        ("Projects", "title"),
        ("Ideas", "title"),
        ("Admin", "title"),
    ],
)
async def test_file_capture_each_bucket(
    mock_cosmos_manager: object,
    bucket: str,
    field_name: str,
) -> None:
    """Each bucket receives the doc with correct field (name vs title)."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, bucket)

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.file_capture(
        text="Meet Sarah tomorrow at 3pm",
        bucket=bucket,
        confidence=0.80,
        status="classified",
        title="Meeting with Sarah",
    )

    assert result["bucket"] == bucket

    bucket_body = _get_body(mock_cosmos_manager, bucket)
    assert bucket_body[field_name] == "Meeting with Sarah"
    assert bucket_body["rawText"] == "Meet Sarah tomorrow at 3pm"


# ---------------------------------------------------------------------------
# Tests: file_capture -- invalid bucket
# ---------------------------------------------------------------------------


async def test_file_capture_invalid_bucket(
    mock_cosmos_manager: object,
) -> None:
    """Invalid bucket returns error dict with no container writes."""
    tools = _make_tools(mock_cosmos_manager)
    result = await tools.file_capture(
        text="Meet Sarah tomorrow at 3pm",
        bucket="Unknown",
        confidence=0.90,
        status="classified",
        title="Meeting with Sarah",
    )

    assert isinstance(result, dict)
    assert result["error"] == "invalid_bucket"
    assert "Unknown" in result["detail"]

    # No writes to any container
    for name in ("Inbox", "People", "Projects", "Ideas", "Admin"):
        container = mock_cosmos_manager.get_container(name)
        container.create_item.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: confidence clamping
# ---------------------------------------------------------------------------


async def test_file_capture_confidence_clamping_high(
    mock_cosmos_manager: object,
) -> None:
    """Confidence > 1.0 is clamped to 1.0."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.file_capture(
        text="Test clamping",
        bucket="Projects",
        confidence=1.5,
        status="classified",
        title="Clamp Test",
    )

    assert result["confidence"] == 1.0

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    assert inbox_body["classificationMeta"]["confidence"] == 1.0


async def test_file_capture_confidence_clamping_negative(
    mock_cosmos_manager: object,
) -> None:
    """Confidence < 0.0 clamped to 0.0 then defaulted to 0.75."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.file_capture(
        text="Test clamping",
        bucket="Projects",
        confidence=-0.1,
        status="classified",
        title="Clamp Test",
    )

    # After clamping -0.1 -> 0.0, the 0.0 fallback applies: default 0.75
    assert result["confidence"] == 0.75

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    assert inbox_body["classificationMeta"]["confidence"] == 0.75


# ---------------------------------------------------------------------------
# Tests: classification meta fields
# ---------------------------------------------------------------------------


async def test_classification_meta_fields(
    mock_cosmos_manager: object,
) -> None:
    """ClassificationMeta has all required fields with updated agentChain."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    await tools.file_capture(
        text="Build API",
        bucket="Projects",
        confidence=0.75,
        status="classified",
        title="API Build",
    )

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    meta = inbox_body["classificationMeta"]

    # All required fields present
    assert meta["bucket"] == "Projects"
    assert meta["confidence"] == 0.75
    assert meta["allScores"] == {}
    assert meta["classifiedBy"] == "Classifier"
    assert meta["agentChain"] == ["Classifier"]
    assert "classifiedAt" in meta


# ---------------------------------------------------------------------------
# Tests: bidirectional links
# ---------------------------------------------------------------------------


async def test_bidirectional_links(
    mock_cosmos_manager: object,
) -> None:
    """Inbox filedRecordId matches bucket doc id, and vice versa."""
    _setup_echo(mock_cosmos_manager, "Inbox")
    _setup_echo(mock_cosmos_manager, "Projects")

    tools = _make_tools(mock_cosmos_manager)
    await tools.file_capture(
        text="Link test",
        bucket="Projects",
        confidence=0.90,
        status="classified",
        title="Link Test",
    )

    inbox_body = _get_body(mock_cosmos_manager, "Inbox")
    projects_body = _get_body(mock_cosmos_manager, "Projects")

    # Bi-directional link: inbox -> bucket and bucket -> inbox
    assert inbox_body["filedRecordId"] == projects_body["id"]
    assert projects_body["inboxRecordId"] == inbox_body["id"]
