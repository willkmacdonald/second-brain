"""Settings validation tests (Phase 25 -- REQ-SD-05)."""

import pytest
from pydantic import ValidationError

from second_brain.config import Settings


def test_inbox_filed_retention_days_default_is_30() -> None:
    """Default retention is 30 days (env var unset)."""
    s = Settings()
    assert s.inbox_filed_retention_days == 30


def test_inbox_filed_retention_days_accepts_positive_int() -> None:
    """Explicit positive integers (e.g., 14) are accepted."""
    s = Settings(inbox_filed_retention_days=14)
    assert s.inbox_filed_retention_days == 14


def test_inbox_filed_retention_days_min_validation_rejects_zero() -> None:
    """ge=1 constraint rejects 0 (would set ttl=0 = immediate purge).

    Landmine #7 in RESEARCH.md: without ge=1, a misconfigured
    INBOX_FILED_RETENTION_DAYS=0 env var would result in doc["ttl"]=0,
    causing immediate deletion at the next Cosmos TTL sweep. Pydantic
    fails fast at Settings construction.
    """
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        Settings(inbox_filed_retention_days=0)


def test_inbox_filed_retention_days_min_validation_rejects_negative() -> None:
    """ge=1 also rejects negative values."""
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        Settings(inbox_filed_retention_days=-1)
