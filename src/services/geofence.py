import math
from dataclasses import dataclass
from datetime import datetime, timezone


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_m * c


@dataclass
class GeofenceState:
    outside_count: int = 0
    last_alert_at: datetime | None = None


class GeofenceEngine:
    def __init__(self, confirmations_required: int, cooldown_sec: int):
        self.confirmations_required = confirmations_required
        self.cooldown_sec = cooldown_sec
        self.state = GeofenceState()

    def check(
        self,
        lat: float,
        lon: float,
        center_lat: float,
        center_lon: float,
        radius_m: float,
    ) -> tuple[bool, float, bool]:
        distance_m = haversine_m(lat, lon, center_lat, center_lon)
        inside = distance_m <= radius_m

        if inside:
            self.state.outside_count = 0
            return True, distance_m, False

        self.state.outside_count += 1
        if self.state.outside_count < self.confirmations_required:
            return False, distance_m, False

        now = datetime.now(tz=timezone.utc)
        if self.state.last_alert_at is None:
            self.state.last_alert_at = now
            return False, distance_m, True

        if (now - self.state.last_alert_at).total_seconds() >= self.cooldown_sec:
            self.state.last_alert_at = now
            return False, distance_m, True
        return False, distance_m, False
