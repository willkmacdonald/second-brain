"""Runs each canonical query against legacy + spine paths and compares."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ParityResult:
    """Outcome of one parity comparison."""

    tool_name: str
    args: dict[str, Any]
    legacy_ok: bool
    spine_ok: bool
    matched: bool
    diff_summary: str
    timestamp: datetime


async def run_parity(
    legacy_tool: Callable[..., Awaitable[Any]],
    spine_tool: Callable[..., Awaitable[Any]],
    tool_name: str,
    args: dict[str, Any],
) -> ParityResult:
    """Call both paths, compare the JSON-serializable shapes.

    Both tools are called with the provided args as keyword arguments.
    Exceptions are caught and recorded — a failure on either side causes
    matched=False without raising.
    """
    now = datetime.now(UTC)
    legacy_result: Any = None
    spine_result: Any = None
    legacy_ok = False
    spine_ok = False

    try:
        legacy_result = await legacy_tool(**args)
        legacy_ok = True
    except Exception as exc:
        logger.warning("Legacy %s failed: %s", tool_name, exc)

    try:
        spine_result = await spine_tool(**args)
        spine_ok = True
    except Exception as exc:
        logger.warning("Spine %s failed: %s", tool_name, exc)

    matched = False
    diff_summary = ""
    if legacy_ok and spine_ok:
        matched, diff_summary = _compare_shapes(legacy_result, spine_result)
    elif legacy_ok != spine_ok:
        diff_summary = (
            f"only one path returned: legacy_ok={legacy_ok} spine_ok={spine_ok}"
        )

    return ParityResult(
        tool_name=tool_name,
        args=args,
        legacy_ok=legacy_ok,
        spine_ok=spine_ok,
        matched=matched,
        diff_summary=diff_summary,
        timestamp=now,
    )


def _compare_shapes(a: Any, b: Any) -> tuple[bool, str]:
    """Compare two result shapes for parity after normalizing ephemeral fields."""
    try:
        a_json = json.dumps(_normalize(a), sort_keys=True)
        b_json = json.dumps(_normalize(b), sort_keys=True)
    except (TypeError, ValueError) as exc:
        return False, f"serialization error: {exc}"
    if a_json == b_json:
        return True, ""
    return False, _diff_summary(a, b)


# Keys that are intrinsically time-dependent and should be excluded from comparison.
# Extending this set is the correct way to suppress known-volatile fields.
# 'source' is a non-semantic path marker the spine transformers stamp on
# every response ('source: "spine"'); it never appears on the legacy side
# and shouldn't contribute to shape divergence.
_EPHEMERAL_KEYS = frozenset(
    {
        "timestamp",
        "generated_at",
        "last_updated",
        "freshness_seconds",
        "query_latency_ms",
        "source",
    }
)


def _normalize(value: Any) -> Any:
    """Recursively strip ephemeral keys so timestamp drift doesn't cause false failures.

    Operates on dicts, lists, and scalars — anything JSON-serializable.
    """
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items() if k not in _EPHEMERAL_KEYS}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def _diff_summary(a: Any, b: Any) -> str:
    """Return a brief human-readable description of the first divergence found."""
    # Operate on normalized copies so ephemeral keys don't appear in the summary.
    a = _normalize(a)
    b = _normalize(b)

    if type(a) is not type(b):
        return f"type mismatch: {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        keys_a = set(a.keys())
        keys_b = set(b.keys())
        if keys_a != keys_b:
            return (
                f"key mismatch: only_in_a={keys_a - keys_b} only_in_b={keys_b - keys_a}"
            )
        for k in keys_a:
            if a[k] != b[k]:
                return f"value mismatch at key '{k}'"
    if isinstance(a, list) and len(a) != len(b):
        return f"length mismatch: {len(a)} vs {len(b)}"
    return "shapes differ"
