import importlib

from fastapi.testclient import TestClient

from app.config import get_settings


def _build_app() -> object:
    import app.main as main_module

    main_module = importlib.reload(main_module)
    return main_module.create_app()


def test_ui_route_serves_html(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "ui_route_test.db"
    monkeypatch.setenv("TRANSCRIPT_DATABASE_PATH", str(db_path))
    get_settings.cache_clear()

    app = _build_app()
    client = TestClient(app)

    response = client.get("/ui")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Transcript Analyzer UI" in response.text
