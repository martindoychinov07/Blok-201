from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.memory import router as memory_router
from app.api.transcripts import router as transcripts_router
from app.config import get_settings
from app.db import get_connection, init_db
from app.services.analysis_webhook import AnalysisWebhookPublisher
from app.services.fallback_extractor import FallbackExtractor
from app.services.gemini_service import GeminiService
from app.services.memory_service import MemoryService
from app.services.transcription_service import AudioTranscriptionService
from app.services.transcript_service import TranscriptService


def create_app() -> FastAPI:
    settings = get_settings()

    conn = get_connection(settings.transcript_database_path)
    init_db(conn)

    gemini_prompt_path = Path(__file__).resolve().parent / "prompts" / "extraction_prompt.txt"

    gemini_service = GeminiService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_sec=settings.gemini_timeout_sec,
        prompt_path=str(gemini_prompt_path),
    )
    memory_service = MemoryService(conn)
    fallback_extractor = FallbackExtractor()
    analysis_webhook = AnalysisWebhookPublisher(
        enabled=settings.analysis_webhook_enabled,
        url=settings.analysis_webhook_url,
        timeout_sec=settings.analysis_webhook_timeout_sec,
        bearer_token=settings.analysis_webhook_bearer_token,
    )
    transcription_service = AudioTranscriptionService(
        model_name=settings.transcription_model,
        device=settings.transcription_device,
        compute_type=settings.transcription_compute_type,
        language=settings.transcription_language,
    )
    transcript_service = TranscriptService(
        gemini_service=gemini_service,
        memory_service=memory_service,
        fallback_extractor=fallback_extractor,
        fallback_enabled=settings.gemini_fallback_enabled,
        analysis_webhook=analysis_webhook,
    )

    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    app.state.conn = conn
    app.state.gemini_service = gemini_service
    app.state.fallback_extractor = fallback_extractor
    app.state.transcription_service = transcription_service
    app.state.memory_service = memory_service
    app.state.transcript_service = transcript_service
    app.state.analysis_webhook = analysis_webhook

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    web_index = Path(__file__).resolve().parent / "web" / "index.html"

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "status": "ok",
            "docs": "/docs",
            "analyze_endpoint": "/transcripts/analyze",
            "analyze_plain_endpoint": "/transcripts/analyze-plain",
            "ui": "/ui",
            "webhook_enabled": str(settings.analysis_webhook_enabled).lower(),
            "webhook_url": settings.analysis_webhook_url,
        }

    @app.get("/ui")
    async def ui() -> FileResponse:
        return FileResponse(web_index)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        try:
            conn.close()
        except Exception:
            pass

    app.include_router(transcripts_router)
    app.include_router(memory_router)
    return app


app = create_app()
