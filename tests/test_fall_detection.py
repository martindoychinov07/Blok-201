from datetime import datetime, timedelta, timezone

from src.services.fall_detection import FallDetector


def test_fall_detection_after_impact_and_inactivity() -> None:
    detector = FallDetector(impact_threshold=2.5, inactivity_sec=3)
    t0 = datetime.now(tz=timezone.utc)

    assert detector.update(2.7, 0.1, 0.1, ts=t0) is None
    assert detector.update(1.0, 0.0, 0.0, ts=t0 + timedelta(seconds=1)) is None
    evt = detector.update(1.01, 0.01, 0.01, ts=t0 + timedelta(seconds=4))

    assert evt is not None
    assert evt.impact_g >= 2.5
