"""Phase 3: registry includes cosmos and external_services."""

from second_brain.spine.registry import get_default_registry


def test_registry_includes_cosmos() -> None:
    cfg = get_default_registry().get("cosmos")
    assert cfg.host_segment is None  # Cosmos is independent of Container App
    assert cfg.acceptable_lag_seconds >= 300  # diagnostic logs lag 5-10min


def test_registry_includes_external_services() -> None:
    cfg = get_default_registry().get("external_services")
    assert cfg.host_segment == "container_app"
    assert cfg.display_name == "External Services"
