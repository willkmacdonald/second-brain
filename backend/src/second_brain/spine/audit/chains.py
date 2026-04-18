"""Expected segment chains per correlation_kind.

Hardcoded in code (not config) — same principle as the evaluator registry.
When adding a new segment or routing path, update EXPECTED_CHAINS here.
"""

from __future__ import annotations

from dataclasses import dataclass

from second_brain.spine.models import CorrelationKind


@dataclass(frozen=True, slots=True)
class ExpectedSegment:
    """One segment in an expected correlation chain."""

    segment_id: str
    required: bool


EXPECTED_CHAINS: dict[CorrelationKind, list[ExpectedSegment]] = {
    "capture": [
        ExpectedSegment("mobile_capture", required=True),
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("classifier", required=True),
        ExpectedSegment("admin", required=False),
        ExpectedSegment("external_services", required=False),
        ExpectedSegment("cosmos", required=False),
    ],
    "thread": [
        ExpectedSegment("investigation", required=True),
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("cosmos", required=False),
    ],
    "request": [
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("cosmos", required=True),
    ],
    "crud": [
        ExpectedSegment("mobile_ui", required=True),
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("cosmos", required=True),
    ],
}


def get_expected_chain(kind: CorrelationKind) -> list[ExpectedSegment]:
    """Return the expected segment chain for a correlation kind."""
    return EXPECTED_CHAINS[kind]


def required_segments(kind: CorrelationKind) -> list[str]:
    """Return only the required segment_ids in chain order."""
    return [s.segment_id for s in EXPECTED_CHAINS[kind] if s.required]
