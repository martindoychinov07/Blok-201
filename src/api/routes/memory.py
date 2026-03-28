from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/patients", tags=["memory"])


class RememberRequest(BaseModel):
    text: str = Field(min_length=1)
    create_reminder: bool = False
    due_at: str | None = None
    priority: str = "medium"


class ReminderStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|done|cancelled|stale)$")


@router.get("/{patient_id}/memory")
async def list_memory(patient_id: str, request: Request, limit: int = 100) -> list[dict]:
    repo = request.app.state.repo
    profile = repo.get_patient_profile(patient_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return repo.list_memory(patient_id=patient_id, limit=limit)


@router.get("/{patient_id}/context")
async def get_context(patient_id: str, request: Request) -> dict:
    repo = request.app.state.repo
    profile = repo.get_patient_profile(patient_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return repo.get_memory_context(patient_id)


@router.get("/{patient_id}/reminders")
async def list_reminders(patient_id: str, request: Request, status: str = "active", limit: int = 100) -> list[dict]:
    repo = request.app.state.repo
    profile = repo.get_patient_profile(patient_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return repo.list_reminders(patient_id=patient_id, status=status, limit=limit)


@router.get("/{patient_id}/events")
async def list_events(patient_id: str, request: Request, limit: int = 100) -> list[dict]:
    repo = request.app.state.repo
    profile = repo.get_patient_profile(patient_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return repo.list_events(patient_id=patient_id, limit=limit)


@router.post("/{patient_id}/remember")
async def remember_item(patient_id: str, payload: RememberRequest, request: Request) -> dict:
    repo = request.app.state.repo
    profile = repo.get_patient_profile(patient_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    fact_id = repo.add_or_merge_fact(
        patient_id=patient_id,
        conversation_id=None,
        fact_type="memory_note",
        subject_ref="patient",
        predicate="manual_note",
        object_value=payload.text,
        confidence=1.0,
        source_evidence="manual_dashboard_entry",
    )

    reminder_id = None
    if payload.create_reminder:
        reminder_id = repo.add_or_merge_reminder(
            patient_id=patient_id,
            source_conversation_id=None,
            title="Manual remember note",
            details=payload.text,
            due_at=payload.due_at,
            recurrence_rule=None,
            priority=payload.priority,
            confidence=1.0,
        )

    return {"ok": True, "fact_id": fact_id, "reminder_id": reminder_id}


@router.patch("/{patient_id}/reminders/{reminder_id}")
async def update_reminder_status(patient_id: str, reminder_id: str, payload: ReminderStatusRequest, request: Request) -> dict:
    repo = request.app.state.repo
    profile = repo.get_patient_profile(patient_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    ok = repo.set_reminder_status(patient_id=patient_id, reminder_id=reminder_id, status=payload.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"ok": True, "reminder_id": reminder_id, "status": payload.status}
