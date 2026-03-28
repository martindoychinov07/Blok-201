from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/patients", tags=["memory"])


class ReminderStatusIn(BaseModel):
    status: str = Field(pattern="^(active|done|cancelled|stale)$")


@router.get("/{patient_id}/reminders")
async def get_reminders(patient_id: str, request: Request, status: str = "active", limit: int = 50) -> list[dict]:
    memory_service = request.app.state.memory_service
    status = status.strip().lower()
    if status not in {"active", "done", "cancelled", "stale", "all"}:
        raise HTTPException(status_code=400, detail="Invalid status filter")
    return memory_service.list_reminders(patient_id=patient_id, status=status, limit=max(1, min(limit, 200)))


@router.patch("/{patient_id}/reminders/{reminder_id}")
async def patch_reminder_status(patient_id: str, reminder_id: int, payload: ReminderStatusIn, request: Request) -> dict:
    memory_service = request.app.state.memory_service
    ok = memory_service.update_reminder_status(patient_id=patient_id, reminder_id=reminder_id, status=payload.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"ok": True, "reminder_id": reminder_id, "status": payload.status}


@router.get("/{patient_id}/appointments")
async def get_appointments(patient_id: str, request: Request, limit: int = 30) -> list[dict]:
    memory_service = request.app.state.memory_service
    return memory_service.list_appointments(patient_id=patient_id, limit=max(1, min(limit, 200)))


@router.get("/{patient_id}/facts")
async def get_facts(patient_id: str, request: Request, limit: int = 50) -> list[dict]:
    memory_service = request.app.state.memory_service
    return memory_service.list_facts(patient_id=patient_id, limit=max(1, min(limit, 300)))


@router.get("/{patient_id}/transcripts")
async def get_transcripts(patient_id: str, request: Request, limit: int = 20) -> list[dict]:
    memory_service = request.app.state.memory_service
    return memory_service.list_recent_transcripts(patient_id=patient_id, limit=max(1, min(limit, 100)))
