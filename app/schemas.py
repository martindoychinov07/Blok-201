from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TranscriptIn(BaseModel):
    patient_id: str = Field(min_length=1)
    timestamp: datetime
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text cannot be empty")
        return cleaned


class Person(BaseModel):
    name: str = Field(min_length=1)
    relationship: str | None = None


class Appointment(BaseModel):
    title: str = Field(min_length=1)
    doctor: str | None = None
    time_text: str | None = None


class Reminder(BaseModel):
    type: str = Field(min_length=1)
    text: str = Field(min_length=1)
    time_text: str | None = None


class AnalysisResult(BaseModel):
    people: list[Person] = Field(default_factory=list)
    appointments: list[Appointment] = Field(default_factory=list)
    reminders: list[Reminder] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    important_facts: list[str] = Field(default_factory=list)


class TranscriptAnalyzeResponse(BaseModel):
    transcript_id: int
    analysis: AnalysisResult
    saved: dict[str, int]
    source: str = "gemini"
    warning: str | None = None


class AudioTranscribeResponse(BaseModel):
    text: str
    duration_seconds: float
    analysis: TranscriptAnalyzeResponse | None = None
