import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import AudioTranscribeResponse, TranscriptAnalyzeResponse, TranscriptIn
from app.services.gemini_service import GeminiInvalidResponseError, GeminiMissingApiKeyError, GeminiServiceError
from app.services.transcription_service import (
    InvalidWavAudioError,
    TranscriptionEngineMissingError,
    TranscriptionServiceError,
)

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


def _analyze_and_build_response(request: Request, payload: TranscriptIn) -> TranscriptAnalyzeResponse:
    transcript_service = request.app.state.transcript_service
    try:
        transcript_id, analysis, saved, source, warning = transcript_service.analyze_and_persist(payload)
    except GeminiMissingApiKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except GeminiInvalidResponseError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini invalid response: {exc}") from exc
    except GeminiServiceError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database write failed: {exc}") from exc

    return TranscriptAnalyzeResponse(
        transcript_id=transcript_id,
        analysis=analysis,
        saved=saved,
        source=source,
        warning=warning,
    )


def _parse_iso_timestamp(timestamp: str | None) -> datetime:
    if not timestamp:
        return datetime.now(tz=timezone.utc)
    ts = timestamp.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="timestamp must be ISO-8601") from exc


@router.post("/analyze", response_model=TranscriptAnalyzeResponse)
async def analyze_transcript(payload: TranscriptIn, request: Request) -> TranscriptAnalyzeResponse:
    return _analyze_and_build_response(request, payload)


@router.post("/analyze-plain", response_model=TranscriptAnalyzeResponse)
async def analyze_transcript_plain(
    request: Request,
    patient_id: str | None = Query(default=None),
    timestamp: str | None = Query(default=None),
) -> TranscriptAnalyzeResponse:
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty text payload")

    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Text payload must be UTF-8") from exc

    if not text:
        raise HTTPException(status_code=400, detail="text cannot be empty")

    settings = request.app.state.settings
    resolved_patient_id = (patient_id or settings.default_patient_id).strip()
    if not resolved_patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required")

    transcript_payload = TranscriptIn(
        patient_id=resolved_patient_id,
        timestamp=_parse_iso_timestamp(timestamp),
        text=text,
    )
    return _analyze_and_build_response(request, transcript_payload)


@router.post("/transcribe", response_model=AudioTranscribeResponse)
async def transcribe_wav(
    request: Request,
    patient_id: str | None = Query(default=None),
    analyze: bool = Query(default=True),
    timestamp: str | None = Query(default=None),
) -> AudioTranscribeResponse:
    content_type = (request.headers.get("content-type") or "").lower()
    allowed_types = ("audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream")
    if not any(t in content_type for t in allowed_types):
        raise HTTPException(status_code=415, detail="Content-Type must be audio/wav")

    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio payload")

    settings = request.app.state.settings
    max_bytes = int(settings.max_audio_upload_mb) * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Audio file too large. Limit is {settings.max_audio_upload_mb} MB")

    transcription_service = request.app.state.transcription_service
    try:
        transcript_text, duration_seconds = transcription_service.transcribe_wav_bytes(audio_bytes)
    except TranscriptionEngineMissingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidWavAudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TranscriptionServiceError as exc:
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}") from exc

    analysis_payload = None
    if analyze:
        resolved_patient_id = (patient_id or settings.default_patient_id).strip()
        if not resolved_patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required when analyze=true")

        resolved_timestamp = _parse_iso_timestamp(timestamp)

        transcript_payload = TranscriptIn(
            patient_id=resolved_patient_id,
            timestamp=resolved_timestamp,
            text=transcript_text,
        )
        analysis_payload = _analyze_and_build_response(request, transcript_payload)

    return AudioTranscribeResponse(
        text=transcript_text,
        duration_seconds=duration_seconds,
        analysis=analysis_payload,
    )
