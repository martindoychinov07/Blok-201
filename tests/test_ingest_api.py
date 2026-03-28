from fastapi.testclient import TestClient
import importlib

from src.config.settings import get_settings


def _build_app() -> object:
    import src.api.app as app_module

    app_module = importlib.reload(app_module)
    return app_module.create_app()


def test_ingest_requires_device_key(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("INGEST_SHARED_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/mvp_test_ingest_1.db")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    no_key = client.post("/ingest/transcript", json={"text": "Maria will visit tomorrow."})
    assert no_key.status_code == 401

    ok = client.post(
        "/ingest/transcript",
        json={"text": "Maria will visit tomorrow."},
        headers={"X-Device-Key": "test-key"},
    )
    assert ok.status_code == 200


def test_ingest_accepts_new_device_id(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("INGEST_SHARED_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/mvp_test_ingest_2.db")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    ok = client.post(
        "/ingest/transcript",
        json={
            "text": "I might have fallen.",
            "patient_id": "patient-001",
            "device_id": "pc-001",
        },
        headers={"X-Device-Key": "test-key"},
    )
    assert ok.status_code == 200


def test_ingest_unknown_patient_returns_404(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("INGEST_SHARED_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/mvp_test_ingest_3.db")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    bad = client.post(
        "/ingest/transcript",
        json={"text": "hello", "patient_id": "missing-patient", "device_id": "pc-001"},
        headers={"X-Device-Key": "test-key"},
    )
    assert bad.status_code == 404


def test_manual_remember_creates_memory_note(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("INGEST_SHARED_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/mvp_test_ingest_4.db")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    res = client.post(
        "/patients/patient-001/remember",
        json={"text": "Remember that my favorite drink is tea.", "create_reminder": True},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is True
    assert payload["fact_id"]


def test_reminders_stack_with_different_details(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("INGEST_SHARED_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/mvp_test_ingest_5.db")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    r1 = client.post(
        "/patients/patient-001/remember",
        json={"text": "Take blue pills every morning", "create_reminder": True},
    )
    r2 = client.post(
        "/patients/patient-001/remember",
        json={"text": "Take blood pressure pill every evening", "create_reminder": True},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    reminders = client.get("/patients/patient-001/reminders?status=active&limit=50").json()
    assert len(reminders) >= 2


def test_reminder_status_update(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("INGEST_SHARED_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/mvp_test_ingest_6.db")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    created = client.post(
        "/patients/patient-001/remember",
        json={"text": "Take medicine tonight", "create_reminder": True},
    ).json()

    reminder_id = created["reminder_id"]
    assert reminder_id

    patch_res = client.patch(
        f"/patients/patient-001/reminders/{reminder_id}",
        json={"status": "done"},
    )
    assert patch_res.status_code == 200
    done_list = client.get("/patients/patient-001/reminders?status=done&limit=10").json()
    assert any(r["id"] == reminder_id for r in done_list)


def test_events_endpoint_returns_social_events(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("INGEST_SHARED_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/mvp_test_ingest_7.db")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    client.post(
        "/ingest/transcript",
        json={
            "text": "I am invited to a birthday party on saturday.",
            "patient_id": "patient-001",
            "device_id": "pc-001",
            "flush": True,
        },
        headers={"X-Device-Key": "test-key"},
    )

    events = client.get("/patients/patient-001/events?limit=20").json()
    assert events
    assert any("party" in (e.get("title", "").lower() + " " + (e.get("details", "").lower())) for e in events)


def test_transcript_flush_without_text_processes_buffer(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("INGEST_SHARED_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/mvp_test_ingest_8.db")
    get_settings.cache_clear()
    app = _build_app()
    client = TestClient(app)

    # Simulate ongoing speech chunks without immediate flush.
    r1 = client.post(
        "/ingest/transcript",
        json={"text": "Трябва да отидеш на доктор", "patient_id": "patient-001", "device_id": "pc-001", "flush": False},
        headers={"X-Device-Key": "test-key"},
    )
    r2 = client.post(
        "/ingest/transcript",
        json={"text": "в петък в 12:00.", "patient_id": "patient-001", "device_id": "pc-001", "flush": False},
        headers={"X-Device-Key": "test-key"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    # Flush by silence marker (no text).
    flush = client.post(
        "/ingest/transcript",
        json={"patient_id": "patient-001", "device_id": "pc-001", "flush": True},
        headers={"X-Device-Key": "test-key"},
    )
    assert flush.status_code == 200

    reminders = client.get("/patients/patient-001/reminders?status=active&limit=20").json()
    assert any(r["title"].startswith("Medical appointment") for r in reminders)
