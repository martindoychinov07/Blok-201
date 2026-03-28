from pydantic import BaseModel, Field


class Urgency(BaseModel):
    level: str = Field(default="info")
    reason: str = Field(default="")
    confidence: float = Field(default=0.5)


class ExtractedPerson(BaseModel):
    name: str
    person_type: str = "other"
    relationship_to_patient: str = "known_person"
    confidence: float = 0.6
    source_evidence: list[str] = Field(default_factory=list)


class Reminder(BaseModel):
    title: str
    details: str = ""
    due_at: str | None = None
    recurrence_rule: str | None = None
    priority: str = "medium"
    confidence: float = 0.6
    source_evidence: list[str] = Field(default_factory=list)


class SafetyRisk(BaseModel):
    risk_type: str
    severity: str = "medium"
    description: str
    confidence: float = 0.6
    source_evidence: list[str] = Field(default_factory=list)


class Incident(BaseModel):
    incident_type: str
    description: str
    severity: str = "warning"
    confidence: float = 0.6


class MemoryNote(BaseModel):
    note: str
    category: str = "general"
    confidence: float = 0.6
    source_evidence: list[str] = Field(default_factory=list)


class TranscriptAnalysisResult(BaseModel):
    schema_version: str = "1.0"
    conversation_id: str
    summary_text: str
    urgency: Urgency
    people: list[ExtractedPerson] = Field(default_factory=list)
    reminders: list[Reminder] = Field(default_factory=list)
    memory_notes: list[MemoryNote] = Field(default_factory=list)
    safety_risks: list[SafetyRisk] = Field(default_factory=list)
    incidents: list[Incident] = Field(default_factory=list)
