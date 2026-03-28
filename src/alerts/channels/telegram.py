import httpx


class TelegramChannel:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, title: str, message: str) -> None:
        if not self.bot_token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": f"{title}\n{message}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.post(url, json=payload)
            except Exception:
                # Notification failures should not crash event processing.
                return
