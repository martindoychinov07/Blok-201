from datetime import timezone

import httpx

from app.schemas import AnalysisResult, TranscriptIn


class AnalysisWebhookPublisher:
    def __init__(self, enabled: bool, url: str, timeout_sec: int, bearer_token: str | None = None):
        self.enabled = enabled
        self.url = (url or "").strip()
        self.timeout_sec = timeout_sec
        self.bearer_token = (bearer_token or "").strip() or None

    def publish_analysis_event(
        self,
        *,
        transcript_id: int,
        payload: TranscriptIn,
        analysis: AnalysisResult,
        saved: dict[str, int],
        source: str,
        warning: str | None,
    ) -> str | None:
        if not self.enabled:
            return None
        if not self.url:
            return "Webhook sync failed: ANALYSIS_WEBHOOK_URL is not configured"

        ts = payload.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        body = {
            "transcript_id": transcript_id,
            "patient_id": payload.patient_id,
            "timestamp": ts.isoformat(),
            "text": payload.text,
            "source": source,
            "warning": warning,
            "saved": saved,
            "analysis": analysis.model_dump(),
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        try:
            response = httpx.post(self.url, json=body, headers=headers, timeout=self.timeout_sec)
            response.raise_for_status()
            return None
        except Exception as exc:
            return f"Webhook sync failed: {self._compact_error(exc)}"

    def _compact_error(self, exc: Exception) -> str:
        msg = str(exc).strip().replace("\n", " ")
        if len(msg) > 180:
            return msg[:177] + "..."
        return msg or exc.__class__.__name__
