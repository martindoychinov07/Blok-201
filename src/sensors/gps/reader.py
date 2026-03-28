import asyncio
import random
from dataclasses import dataclass

from src.services.event_bus import EventBus


@dataclass
class GPSService:
    bus: EventBus
    interval_sec: int = 5
    center_lat: float = 42.6977
    center_lon: float = 23.3219

    async def run(self) -> None:
        lat = self.center_lat
        lon = self.center_lon
        while True:
            # Random walk with occasional larger jump to simulate geofence breach.
            lat += random.uniform(-0.0002, 0.0002)
            lon += random.uniform(-0.0002, 0.0002)
            if random.random() < 0.08:
                lat += random.uniform(0.002, 0.004)
                lon += random.uniform(0.002, 0.004)

            await self.bus.publish(
                "sensor.gps",
                {
                    "lat": lat,
                    "lon": lon,
                    "speed_mps": random.uniform(0.0, 1.2),
                    "accuracy_m": random.uniform(4.0, 15.0),
                },
            )
            await asyncio.sleep(self.interval_sec)
