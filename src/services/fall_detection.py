from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt


@dataclass
class FallEvent:
    impact_g: float
    inactivity_sec: int
    confidence: float


class FallDetector:
    def __init__(self, impact_threshold: float, inactivity_sec: int):
        self.impact_threshold = impact_threshold
        self.inactivity_sec = inactivity_sec
        self._impact_at: datetime | None = None
        self._impact_g: float = 0.0
        self._magnitudes = deque(maxlen=120)

    def update(self, ax: float, ay: float, az: float, ts: datetime | None = None) -> FallEvent | None:
        ts = ts or datetime.now(tz=timezone.utc)
        g = sqrt(ax * ax + ay * ay + az * az)
        self._magnitudes.append((ts, g))

        if g >= self.impact_threshold:
            self._impact_at = ts
            self._impact_g = g
            return None

        if self._impact_at is None:
            return None

        delta = (ts - self._impact_at).total_seconds()
        if delta < self.inactivity_sec:
            return None

        if self._is_inactive_window(seconds=self.inactivity_sec):
            confidence = min(0.99, 0.65 + min(self._impact_g / 4.0, 0.3))
            evt = FallEvent(
                impact_g=self._impact_g,
                inactivity_sec=self.inactivity_sec,
                confidence=confidence,
            )
            self._impact_at = None
            self._impact_g = 0.0
            return evt

        return None

    def _is_inactive_window(self, seconds: int) -> bool:
        if not self._magnitudes:
            return False
        last_ts = self._magnitudes[-1][0]
        window = [g for ts, g in self._magnitudes if (last_ts - ts).total_seconds() <= seconds]
        if len(window) < 2:
            return False
        max_g = max(window)
        min_g = min(window)
        return (max_g - min_g) < 0.2
