"""Phase 4: registry includes mobile_ui and mobile_capture."""

from second_brain.spine.registry import get_default_registry


def test_registry_includes_mobile_ui() -> None:
    cfg = get_default_registry().get("mobile_ui")
    assert cfg.host_segment is None
    assert cfg.display_name == "Mobile UI"
    assert cfg.liveness_interval_seconds == 300
    assert cfg.workload_window_seconds == 900


def test_registry_includes_mobile_capture() -> None:
    cfg = get_default_registry().get("mobile_capture")
    assert cfg.host_segment is None
    assert cfg.display_name == "Mobile Capture"
    assert cfg.liveness_interval_seconds == 300
    # Capture failures are higher-severity — lower consecutive threshold
    assert cfg.red_thresholds["consecutive_failures"] == 3


def test_registry_total_count_is_nine() -> None:
    """7 prior segments + 2 mobile = 9."""
    assert len(get_default_registry().all()) == 9
