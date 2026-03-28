from dataclasses import dataclass, field
from typing import Any

from src.alerts.channels.telegram import TelegramChannel


@dataclass
class AlertNotifier:
    telegram_enabled: bool = False
    telegram_channel: TelegramChannel | None = None
    ws_broadcast: Any = None

    async def notify(self, payload: dict) -> None:
        title = payload.get("title", "Alert")
        message = payload.get("message", "")

        if self.ws_broadcast is not None:
            await self.ws_broadcast({"event": "alert:new", "data": payload})

        if self.telegram_enabled and self.telegram_channel is not None:
            await self.telegram_channel.send(title=title, message=message)
