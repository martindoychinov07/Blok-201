import asyncio
import sqlite3
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.ai.client import AIClient
from src.alerts.channels.telegram import TelegramChannel
from src.alerts.engine import AlertEngine
from src.alerts.notifier import AlertNotifier
from src.api.routes.alerts import router as alerts_router
from src.api.routes.health import router as health_router
from src.api.routes.ingest import router as ingest_router
from src.api.routes.memory import router as memory_router
from src.api.routes.profiles import router as profiles_router
from src.api.ws import WSManager
from src.config.settings import get_settings
from src.database.connection import get_connection, init_db
from src.database.repositories import Repository
from src.sensors.accelerometer.reader import AccelerometerService
from src.sensors.gps.reader import GPSService
from src.sensors.microphone.capture import MicrophoneService
from src.services.event_bus import EventBus
from src.services.fall_detection import FallDetector
from src.services.geofence import GeofenceEngine
from src.services.pipeline import SensorPipeline, TranscriptPipeline


def create_app() -> FastAPI:
    app = FastAPI(title="Dementia Edge MVP", version="0.1.0")

    settings = get_settings()
    conn = get_connection(settings.database_path)
    schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    init_db(conn, str(schema_path))
    repo = Repository(conn)
    for attempt in range(5):
        try:
            repo.bootstrap_defaults(patient_id=settings.default_patient_id, device_id=settings.default_device_id)
            break
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 4:
                raise
            time.sleep(0.2)

    ws_manager = WSManager()
    telegram = TelegramChannel(settings.notify_telegram_bot_token, settings.notify_telegram_chat_id)
    notifier = AlertNotifier(
        telegram_enabled=settings.notify_telegram_enabled,
        telegram_channel=telegram,
        ws_broadcast=ws_manager.broadcast,
    )
    alert_engine = AlertEngine(
        repo=repo,
        notifier=notifier,
        patient_id=settings.default_patient_id,
        device_id=settings.default_device_id,
    )

    bus = EventBus()
    ai_client = AIClient()

    transcript_pipeline = TranscriptPipeline(
        repo=repo,
        ai_client=ai_client,
        alert_engine=alert_engine,
        patient_id=settings.default_patient_id,
        device_id=settings.default_device_id,
    )

    sensor_pipeline = SensorPipeline(
        repo=repo,
        alert_engine=alert_engine,
        geofence_engine=GeofenceEngine(
            confirmations_required=settings.geofence_exit_confirmations,
            cooldown_sec=settings.geofence_cooldown_sec,
        ),
        fall_detector=FallDetector(
            impact_threshold=settings.fall_impact_g_threshold,
            inactivity_sec=settings.fall_inactivity_sec,
        ),
        patient_id=settings.default_patient_id,
        device_id=settings.default_device_id,
    )

    bus.subscribe("speech.transcript_chunk", transcript_pipeline.handle_transcript_chunk)
    bus.subscribe("sensor.gps", sensor_pipeline.handle_gps)
    bus.subscribe("sensor.accel", sensor_pipeline.handle_accelerometer)

    mic_service = MicrophoneService(bus=bus, interval_sec=settings.demo_transcript_interval_sec)
    gps_service = GPSService(bus=bus, interval_sec=settings.demo_gps_interval_sec)
    accel_service = AccelerometerService(bus=bus, interval_sec=settings.demo_accel_interval_sec)

    app.state.settings = settings
    app.state.repo = repo
    app.state.bus = bus
    app.state.ws_manager = ws_manager
    app.state.transcript_pipeline = transcript_pipeline
    app.state.sensor_pipeline = sensor_pipeline
    app.state.tasks = []

    dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard" / "web"
    app.mount("/dashboard-assets", StaticFiles(directory=str(dashboard_dir)), name="dashboard-assets")

    @app.get("/")
    async def dashboard_index() -> FileResponse:
        return FileResponse(dashboard_dir / "index.html")

    @app.on_event("startup")
    async def startup() -> None:
        app.state.tasks = []
        if settings.demo_mode:
            app.state.tasks = [
                asyncio.create_task(mic_service.run()),
                asyncio.create_task(gps_service.run()),
                asyncio.create_task(accel_service.run()),
            ]

    @app.on_event("shutdown")
    async def shutdown() -> None:
        for task in app.state.tasks:
            task.cancel()
        await asyncio.gather(*app.state.tasks, return_exceptions=True)

    @app.websocket("/ws/alerts")
    async def ws_alerts(websocket: WebSocket) -> None:
        manager: WSManager = app.state.ws_manager
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(alerts_router)
    app.include_router(profiles_router)
    app.include_router(memory_router)
    return app


app = create_app()
