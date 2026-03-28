from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

router = APIRouter(prefix="/ingest", tags=["ingest"])


class TranscriptIngest(BaseModel):
    patient_id: str | None = None
    device_id: str | None = None
    text: str | None = None
    ts_start_ms: int = 0
    ts_end_ms: int = 5000
    stt_engine: str = "esp32-forwarded"
    stt_confidence: float = 0.75
    flush: bool = False

    @model_validator(mode="after")
    def validate_text_or_flush(self) -> "TranscriptIngest":
        if self.flush:
            return self
        if self.text is None or not self.text.strip():
            raise ValueError("text is required when flush is false")
        return self


class GPSIngest(BaseModel):
    patient_id: str | None = None
    device_id: str | None = None
    lat: float
    lon: float
    speed_mps: float = 0.0
    accuracy_m: float = 10.0


class AccelerometerIngest(BaseModel):
    patient_id: str | None = None
    device_id: str | None = None
    ax: float
    ay: float
    az: float


def _validate_key(request: Request, device_key: str | None) -> None:
    expected = request.app.state.settings.ingest_shared_key
    if not expected:
        return
    if device_key != expected:
        raise HTTPException(status_code=401, detail="Invalid device key")


def _resolve_patient_device(request: Request, patient_id: str | None, device_id: str | None) -> tuple[str, str]:
    app_state = request.app.state
    repo = app_state.repo
    pid = patient_id or app_state.settings.default_patient_id
    did = device_id or app_state.settings.default_device_id
    if repo.get_patient_profile(pid) is None:
        raise HTTPException(status_code=404, detail="Unknown patient_id")
    return pid, did


@router.post("/transcript")
async def ingest_transcript(
    payload: TranscriptIngest,
    request: Request,
    x_device_key: str | None = Header(default=None),
) -> dict:
    _validate_key(request, x_device_key)
    app_state = request.app.state
    pid, did = _resolve_patient_device(request, payload.patient_id, payload.device_id)

    accepted = False
    flushed = False

    if payload.text is not None and payload.text.strip():
        await app_state.transcript_pipeline.handle_transcript_chunk(
            {
                "patient_id": pid,
                "device_id": did,
                "text": payload.text.strip(),
                "ts_start_ms": payload.ts_start_ms,
                "ts_end_ms": payload.ts_end_ms,
                "stt_engine": payload.stt_engine,
                "stt_confidence": payload.stt_confidence,
                "flush": False,
            }
        )
        accepted = True

    if payload.flush:
        flushed = await app_state.transcript_pipeline.flush_session(patient_id=pid, device_id=did)

    return {"ok": True, "accepted": accepted, "flushed": flushed}


@router.post("/gps")
async def ingest_gps(
    payload: GPSIngest,
    request: Request,
    x_device_key: str | None = Header(default=None),
) -> dict:
    _validate_key(request, x_device_key)
    app_state = request.app.state
    pid, did = _resolve_patient_device(request, payload.patient_id, payload.device_id)
    await app_state.sensor_pipeline.handle_gps(
        {
            "patient_id": pid,
            "device_id": did,
            "lat": payload.lat,
            "lon": payload.lon,
            "speed_mps": payload.speed_mps,
            "accuracy_m": payload.accuracy_m,
        }
    )
    return {"ok": True}


@router.post("/accelerometer")
async def ingest_accelerometer(
    payload: AccelerometerIngest,
    request: Request,
    x_device_key: str | None = Header(default=None),
) -> dict:
    _validate_key(request, x_device_key)
    app_state = request.app.state
    pid, did = _resolve_patient_device(request, payload.patient_id, payload.device_id)
    await app_state.sensor_pipeline.handle_accelerometer(
        {
            "patient_id": pid,
            "device_id": did,
            "ax": payload.ax,
            "ay": payload.ay,
            "az": payload.az,
        }
    )
    return {"ok": True}
