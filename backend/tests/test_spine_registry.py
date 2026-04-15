"""Tests for per-segment evaluator config registry."""

import pytest

from second_brain.spine.registry import (
    EvaluatorConfig,
    get_default_registry,
)


def test_default_registry_includes_backend_api() -> None:
    registry = get_default_registry()
    cfg = registry.get("backend_api")
    assert cfg.segment_id == "backend_api"
    assert cfg.host_segment == "container_app"
    assert cfg.liveness_interval_seconds == 30


def test_default_registry_includes_container_app_rollup_node() -> None:
    registry = get_default_registry()
    cfg = registry.get("container_app")
    assert cfg.segment_id == "container_app"
    assert cfg.host_segment is None  # the host of others, hosted by nothing


def test_unknown_segment_raises_keyerror() -> None:
    registry = get_default_registry()
    with pytest.raises(KeyError):
        registry.get("nonexistent_segment")


def test_all_returns_all_segments() -> None:
    registry = get_default_registry()
    all_cfgs = registry.all()
    assert len(all_cfgs) == 2
    ids = {c.segment_id for c in all_cfgs}
    assert "backend_api" in ids
    assert "container_app" in ids


def test_evaluator_config_thresholds_have_defaults() -> None:
    cfg = EvaluatorConfig(
        segment_id="test",
        liveness_interval_seconds=30,
        host_segment=None,
    )
    assert cfg.workload_window_seconds == 300
    assert cfg.acceptable_lag_seconds == 0
    assert cfg.yellow_thresholds == {}
    assert cfg.red_thresholds == {}
