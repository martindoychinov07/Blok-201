from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/patients", tags=["profiles"])


@router.get("/{patient_id}/profile")
async def get_patient_profile(patient_id: str, request: Request) -> dict:
    repo = request.app.state.repo
    profile = repo.get_patient_profile(patient_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    people = repo.list_people_profiles(patient_id)
    return {"patient": profile, "people_profiles": people}
