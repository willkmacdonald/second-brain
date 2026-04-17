"""Phase 2: registry includes the three Foundry agent segments."""

from second_brain.spine.registry import get_default_registry


def test_registry_includes_classifier() -> None:
    cfg = get_default_registry().get("classifier")
    assert cfg.host_segment == "container_app"
    assert cfg.display_name == "Classifier"
    assert cfg.yellow_thresholds.get("workload_failure_rate") == 0.20


def test_registry_includes_admin() -> None:
    cfg = get_default_registry().get("admin")
    assert cfg.host_segment == "container_app"


def test_registry_includes_investigation() -> None:
    cfg = get_default_registry().get("investigation")
    assert cfg.host_segment == "container_app"


def test_all_three_agents_have_red_consecutive_failures_threshold() -> None:
    registry = get_default_registry()
    for sid in ("classifier", "admin", "investigation"):
        cfg = registry.get(sid)
        assert cfg.red_thresholds.get("consecutive_failures") == 3
