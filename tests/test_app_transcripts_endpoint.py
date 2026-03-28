import importlib

from fastapi.testclient import TestClient

from app.config import get_settings
from app.schemas import AnalysisResult
from app.services.gemini_service import GeminiServiceError


def _build_app() -> object:
    import app.main as main_module

    main_module = importlib.reload(main_module)
    return main_module.create_app()


def test_transcript_analyze_endpoint_persists_data(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcript_analyze_test.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    get_settings.cache_clear()
    app = _build_app()

    fake_result = AnalysisResult.model_validate(
        {
            "people": [{"name": "Maria", "relationship": "daughter"}],
            "appointments": [{"title": "Doctor appointment", "doctor": "Dr. Ivanov", "time_text": "Tomorrow 3 PM"}],
            "reminders": [{"type": "task", "text": "Take pills", "time_text": "daily morning"}],
            "medications": ["Aspirin"],
            "safety_notes": ["Patient reported confusion"],
            "important_facts": ["Maria will escort patient"],
        }
    )

    def fake_analyze(_: str) -> AnalysisResult:
        return fake_result

    app.state.gemini_service.analyze_transcript = fake_analyze

    client = TestClient(app)
    response = client.post(
        "/transcripts/analyze",
        json={
            "patient_id": "p_001",
            "timestamp": "2026-03-26T14:30:00Z",
            "text": "Tomorrow at 3 PM we have an appointment with Dr. Ivanov.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["transcript_id"] > 0
    assert data["saved"]["people"] >= 1
    assert data["saved"]["appointments"] == 1
    assert data["saved"]["reminders"] >= 1
    assert data["saved"]["facts"] >= 3

    row = app.state.conn.execute("SELECT COUNT(*) AS cnt FROM transcripts WHERE patient_id = ?", ("p_001",)).fetchone()
    assert row["cnt"] == 1


def test_transcript_analyze_endpoint_handles_missing_api_key(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcript_analyze_test_missing_key.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GEMINI_FALLBACK_ENABLED", "false")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    response = client.post(
        "/transcripts/analyze",
        json={
            "patient_id": "p_001",
            "timestamp": "2026-03-26T14:30:00Z",
            "text": "Tomorrow we have an appointment.",
        },
    )

    assert response.status_code == 500
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_transcript_analyze_endpoint_uses_fallback_on_gemini_failure(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcript_analyze_test_fallback.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_FALLBACK_ENABLED", "true")
    get_settings.cache_clear()
    app = _build_app()

    def fail(_: str):
        raise GeminiServiceError("429 RESOURCE_EXHAUSTED")

    app.state.gemini_service.analyze_transcript = fail

    client = TestClient(app)
    response = client.post(
        "/transcripts/analyze",
        json={
            "patient_id": "p_001",
            "timestamp": "2026-03-26T14:30:00Z",
            "text": "Tomorrow at 3 PM doctor appointment.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fallback"
    assert body["warning"] is not None


def test_transcript_analyze_enriches_appointment_into_reminder_and_fact(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcript_analyze_test_enrichment.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_FALLBACK_ENABLED", "true")
    get_settings.cache_clear()
    app = _build_app()

    fake_result = AnalysisResult.model_validate(
        {
            "people": [{"name": "Maria", "relationship": None}],
            "appointments": [{"title": "appointment", "doctor": "Dr. Ivanov", "time_text": "Tomorrow at 3 PM"}],
            "reminders": [],
            "medications": [],
            "safety_notes": [],
            "important_facts": [],
        }
    )

    def fake_analyze(_: str) -> AnalysisResult:
        return fake_result

    app.state.gemini_service.analyze_transcript = fake_analyze

    client = TestClient(app)
    response = client.post(
        "/transcripts/analyze",
        json={
            "patient_id": "p_001",
            "timestamp": "2026-03-26T14:30:00Z",
            "text": "Tomorrow at 3 PM appointment with Dr. Ivanov.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["saved"]["appointments"] == 1
    assert body["saved"]["reminders"] >= 1
    assert body["saved"]["facts"] >= 1
    assert any(r["type"] == "appointment" for r in body["analysis"]["reminders"])


def test_transcript_analyze_splits_long_transcript_into_multiple_tasks(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcript_analyze_test_long_split.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_FALLBACK_ENABLED", "true")
    get_settings.cache_clear()
    app = _build_app()

    # Simulate sparse model output, rely on enrichment split logic.
    app.state.gemini_service.analyze_transcript = lambda _t: AnalysisResult.model_validate(
        {
            "people": [],
            "appointments": [],
            "reminders": [],
            "medications": [],
            "safety_notes": [],
            "important_facts": [],
        }
    )

    text = (
        "Утре в 09:30 трябва да отидеш на преглед при д-р Иванов. "
        "В петък в 14:00 имаш среща при кардиолог. "
        "В събота в 18:30 си поканена на рожден ден. "
        "В понеделник в 10:15 трябва да отидеш до лаборатория."
    )

    client = TestClient(app)
    response = client.post(
        "/transcripts/analyze",
        json={
            "patient_id": "p_001",
            "timestamp": "2026-03-26T14:30:00Z",
            "text": text,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["saved"]["reminders"] >= 4
    assert body["saved"]["appointments"] >= 2


def test_transcript_analyze_drops_whole_transcript_reminder_when_split_items_exist(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcript_analyze_drop_whole_reminder.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_FALLBACK_ENABLED", "true")
    get_settings.cache_clear()
    app = _build_app()

    text = "Tomorrow call Maria, then buy bread, after that take pills at 8 PM."
    app.state.gemini_service.analyze_transcript = lambda _t: AnalysisResult.model_validate(
        {
            "people": [],
            "appointments": [],
            "reminders": [{"type": "task", "text": text, "time_text": None}],
            "medications": [],
            "safety_notes": [],
            "important_facts": [],
        }
    )

    client = TestClient(app)
    response = client.post(
        "/transcripts/analyze",
        json={
            "patient_id": "p_001",
            "timestamp": "2026-03-26T14:30:00Z",
            "text": text,
        },
    )

    assert response.status_code == 200
    body = response.json()
    reminder_texts = [r["text"].strip().lower() for r in body["analysis"]["reminders"]]
    assert text.strip().lower() not in reminder_texts
    assert len(reminder_texts) >= 2


def test_transcript_analyze_keeps_success_when_webhook_sync_fails(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcript_analyze_webhook_bridge.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("ANALYSIS_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("ANALYSIS_WEBHOOK_URL", "https://example.com/hooks/analysis")
    get_settings.cache_clear()
    app = _build_app()

    app.state.gemini_service.analyze_transcript = lambda _t: AnalysisResult.model_validate(
        {
            "people": [],
            "appointments": [],
            "reminders": [{"type": "task", "text": "Call Maria", "time_text": "tomorrow"}],
            "medications": [],
            "safety_notes": [],
            "important_facts": [],
        }
    )
    app.state.analysis_webhook.publish_analysis_event = lambda **_kwargs: "Webhook sync failed: connection refused"

    client = TestClient(app)
    response = client.post(
        "/transcripts/analyze",
        json={
            "patient_id": "p_001",
            "timestamp": "2026-03-26T14:30:00Z",
            "text": "Tomorrow call Maria.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "Webhook sync failed" in (body["warning"] or "")


def test_transcript_analyze_plain_accepts_raw_text_with_defaults(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcript_analyze_plain.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("DEFAULT_PATIENT_ID", "p_default")
    get_settings.cache_clear()
    app = _build_app()

    app.state.gemini_service.analyze_transcript = lambda _t: AnalysisResult.model_validate(
        {
            "people": [{"name": "Maria", "relationship": "daughter"}],
            "appointments": [],
            "reminders": [{"type": "task", "text": "Call Maria", "time_text": "tomorrow"}],
            "medications": [],
            "safety_notes": [],
            "important_facts": ["Call reminder captured"],
        }
    )

    client = TestClient(app)
    response = client.post(
        "/transcripts/analyze-plain",
        data="Tomorrow call Maria and buy aspirin.",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["saved"]["reminders"] >= 1
    row = app.state.conn.execute("SELECT COUNT(*) AS cnt FROM transcripts WHERE patient_id = ?", ("p_default",)).fetchone()
    assert row["cnt"] == 1


def test_transcript_analyze_plain_rejects_empty_body(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcript_analyze_plain_empty.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    response = client.post(
        "/transcripts/analyze-plain",
        data="",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 400
    assert "Empty text payload" in response.json()["detail"]
