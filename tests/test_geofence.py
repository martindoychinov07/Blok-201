from src.services.geofence import GeofenceEngine


def test_geofence_requires_confirmations() -> None:
    engine = GeofenceEngine(confirmations_required=2, cooldown_sec=60)
    inside, _, should_alert = engine.check(42.6977, 23.3219, 42.6977, 23.3219, 100.0)
    assert inside is True
    assert should_alert is False

    inside, _, should_alert = engine.check(42.7100, 23.3400, 42.6977, 23.3219, 100.0)
    assert inside is False
    assert should_alert is False

    inside, _, should_alert = engine.check(42.7102, 23.3402, 42.6977, 23.3219, 100.0)
    assert inside is False
    assert should_alert is True
