import importlib
import io
import wave

from fastapi.testclient import TestClient

from app.config import get_settings
from app.schemas import AnalysisResult


def _build_app() -> object:
    import app.main as main_module

    main_module = importlib.reload(main_module)
    return main_module.create_app()


def _make_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 16000)
    return buffer.getvalue()


def test_transcribe_endpoint_with_analysis(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcribe_endpoint_test.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_FALLBACK_ENABLED", "true")
    get_settings.cache_clear()
    app = _build_app()

    app.state.transcription_service.transcribe_wav_bytes = lambda _b: (
        "Tomorrow at 3 PM appointment with Dr. Ivanov.",
        1.0,
    )

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
    app.state.gemini_service.analyze_transcript = lambda _t: fake_result

    client = TestClient(app)
    response = client.post(
        "/transcripts/transcribe?patient_id=p_001&analyze=true",
        data=_make_wav_bytes(),
        headers={"Content-Type": "audio/wav"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"]
    assert body["analysis"] is not None
    assert body["analysis"]["saved"]["appointments"] == 1


def test_transcribe_endpoint_rejects_non_wav_content_type(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "transcribe_endpoint_bad_type.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    response = client.post(
        "/transcripts/transcribe?patient_id=p_001&analyze=false",
        data=b"plain text",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415
