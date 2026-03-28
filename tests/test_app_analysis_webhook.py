from datetime import datetime, timezone

import httpx

from app.schemas import AnalysisResult, TranscriptIn
from app.services.analysis_webhook import AnalysisWebhookPublisher


def _sample_payload() -> TranscriptIn:
    return TranscriptIn(
        patient_id="p_001",
        timestamp=datetime(2026, 3, 26, 14, 30, tzinfo=timezone.utc),
        text="Tomorrow at 3 PM appointment with Dr. Ivanov.",
    )


def _sample_analysis() -> AnalysisResult:
    return AnalysisResult.model_validate(
        {
            "people": [{"name": "Maria", "relationship": "daughter"}],
            "appointments": [{"title": "Medical appointment", "doctor": "Dr. Ivanov", "time_text": "Tomorrow at 3 PM"}],
            "reminders": [{"type": "appointment", "text": "Attend appointment", "time_text": "Tomorrow at 3 PM"}],
            "medications": [],
            "safety_notes": [],
            "important_facts": [],
        }
    )


def test_webhook_noop_when_disabled(monkeypatch) -> None:
    called = {"value": False}

    def fake_post(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("httpx.post should not be called when disabled")

    monkeypatch.setattr(httpx, "post", fake_post)

    publisher = AnalysisWebhookPublisher(enabled=False, url="https://example.com/hook", timeout_sec=2)
    warning = publisher.publish_analysis_event(
        transcript_id=1,
        payload=_sample_payload(),
        analysis=_sample_analysis(),
        saved={"people": 1, "appointments": 1, "reminders": 1, "facts": 1},
        source="gemini",
        warning=None,
    )

    assert warning is None
    assert called["value"] is False


def test_webhook_posts_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, json: dict, headers: dict, timeout: int):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout

        class Resp:
            def raise_for_status(self) -> None:
                return None

        return Resp()

    monkeypatch.setattr(httpx, "post", fake_post)

    publisher = AnalysisWebhookPublisher(
        enabled=True,
        url="https://example.com/hooks/analysis",
        timeout_sec=3,
        bearer_token="abc123",
    )
    warning = publisher.publish_analysis_event(
        transcript_id=7,
        payload=_sample_payload(),
        analysis=_sample_analysis(),
        saved={"people": 1, "appointments": 1, "reminders": 1, "facts": 1},
        source="gemini",
        warning=None,
    )

    assert warning is None
    assert captured["url"] == "https://example.com/hooks/analysis"
    assert captured["timeout"] == 3
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer abc123",
    }
    body = captured["json"]
    assert body["transcript_id"] == 7
    assert body["patient_id"] == "p_001"
    assert "analysis" in body


def test_webhook_returns_warning_on_failure(monkeypatch) -> None:
    def fail_post(_url: str, json: dict, headers: dict, timeout: int):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(httpx, "post", fail_post)

    publisher = AnalysisWebhookPublisher(enabled=True, url="https://example.com/hook", timeout_sec=3)
    warning = publisher.publish_analysis_event(
        transcript_id=7,
        payload=_sample_payload(),
        analysis=_sample_analysis(),
        saved={"people": 1, "appointments": 1, "reminders": 1, "facts": 1},
        source="gemini",
        warning=None,
    )

    assert warning is not None
    assert warning.startswith("Webhook sync failed:")


def test_webhook_returns_warning_when_url_missing() -> None:
    publisher = AnalysisWebhookPublisher(enabled=True, url="", timeout_sec=3)
    warning = publisher.publish_analysis_event(
        transcript_id=7,
        payload=_sample_payload(),
        analysis=_sample_analysis(),
        saved={"people": 1, "appointments": 1, "reminders": 1, "facts": 1},
        source="gemini",
        warning=None,
    )

    assert warning == "Webhook sync failed: ANALYSIS_WEBHOOK_URL is not configured"
