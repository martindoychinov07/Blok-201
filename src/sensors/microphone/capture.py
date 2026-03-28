import asyncio
from dataclasses import dataclass

from src.services.event_bus import EventBus


DEMO_UTTERANCES = [
    "Maria will visit tomorrow at 10 for a doctor appointment.",
    "I do not remember if I took my pill.",
    "The caregiver said we should rest before dinner.",
    "I feel confused and I do not know where I put my keys.",
    "I might have fallen near the hallway earlier.",
]


@dataclass
class MicrophoneService:
    bus: EventBus
    interval_sec: int = 8

    async def run(self) -> None:
        idx = 0
        while True:
            text = DEMO_UTTERANCES[idx % len(DEMO_UTTERANCES)]
            idx += 1
            await self.bus.publish(
                "speech.transcript_chunk",
                {
                    "text": text,
                    "ts_start_ms": 0,
                    "ts_end_ms": 5000,
                    "stt_engine": "demo-local-stt",
                    "stt_confidence": 0.8,
                },
            )
            await asyncio.sleep(self.interval_sec)
