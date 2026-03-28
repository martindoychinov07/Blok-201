import importlib

from fastapi.testclient import TestClient

from app.config import get_settings
from app.schemas import AnalysisResult


def _build_app() -> object:
    import app.main as main_module

    main_module = importlib.reload(main_module)
    return main_module.create_app()


def test_memory_endpoints_show_and_update_reminders(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "memory_endpoints_test.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_FALLBACK_ENABLED", "true")
    get_settings.cache_clear()
    app = _build_app()

    fake_result = AnalysisResult.model_validate(
        {
            "people": [{"name": "Maria", "relationship": None}],
            "appointments": [{"title": "Doctor appointment", "doctor": "Dr. Ivanov", "time_text": "Tomorrow 3 PM"}],
            "reminders": [{"type": "task", "text": "Bring documents", "time_text": "Tomorrow 2 PM"}],
            "medications": [],
            "safety_notes": [],
            "important_facts": ["Important thing"],
        }
    )

    def fake_analyze(_: str) -> AnalysisResult:
        return fake_result

    app.state.gemini_service.analyze_transcript = fake_analyze
    client = TestClient(app)

    analyze = client.post(
        "/transcripts/analyze",
        json={
            "patient_id": "p_001",
            "timestamp": "2026-03-26T14:30:00Z",
            "text": "Tomorrow doctor appointment with Dr. Ivanov",
        },
    )
    assert analyze.status_code == 200

    reminders = client.get("/patients/p_001/reminders?status=active").json()
    assert len(reminders) >= 1

    reminder_id = reminders[0]["id"]
    patch = client.patch(f"/patients/p_001/reminders/{reminder_id}", json={"status": "done"})
    assert patch.status_code == 200

    done = client.get("/patients/p_001/reminders?status=done").json()
    assert any(r["id"] == reminder_id for r in done)

    appointments = client.get("/patients/p_001/appointments").json()
    assert appointments

    facts = client.get("/patients/p_001/facts").json()
    assert facts
