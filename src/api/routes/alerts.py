from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(request: Request, patient_id: str | None = None, limit: int = 100) -> list[dict]:
    app_state = request.app.state
    repo = app_state.repo
    pid = patient_id or app_state.settings.default_patient_id
    return repo.list_alerts(pid, limit=limit)


@router.post("/{alert_id}/ack")
async def acknowledge_alert(alert_id: str, request: Request, user_id: str = "user-owner") -> dict:
    repo = request.app.state.repo
    success = repo.acknowledge_alert(alert_id=alert_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True, "alert_id": alert_id}
