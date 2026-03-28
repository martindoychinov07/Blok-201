import asyncio
import random
from dataclasses import dataclass

from src.services.event_bus import EventBus


@dataclass
class AccelerometerService:
    bus: EventBus
    interval_sec: int = 1

    async def run(self) -> None:
        while True:
            if random.random() < 0.03:
                # Simulated impact.
                ax, ay, az = random.uniform(2.5, 3.4), random.uniform(0.0, 0.3), random.uniform(0.0, 0.3)
            else:
                ax, ay, az = random.uniform(0.95, 1.05), random.uniform(0.0, 0.1), random.uniform(0.0, 0.1)

            await self.bus.publish("sensor.accel", {"ax": ax, "ay": ay, "az": az})
            await asyncio.sleep(self.interval_sec)
