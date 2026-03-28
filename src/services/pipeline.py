import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.ai.client import AIClient
from src.alerts.engine import AlertEngine
from src.database.repositories import Repository
from src.services.fall_detection import FallDetector
from src.services.geofence import GeofenceEngine


@dataclass
class _SessionState:
    conversation_id: str
    buffer: list[str] = field(default_factory=list)


@dataclass
class _AnalysisJob:
    conversation_id: str
    patient_id: str
    device_id: str
    transcript_text: str


@dataclass
class TranscriptPipeline:
    repo: Repository
    ai_client: AIClient
    alert_engine: AlertEngine
    patient_id: str
    device_id: str
    flush_every_segments: int = 50
    _sessions: dict[tuple[str, str], _SessionState] = field(default_factory=dict)
    _sessions_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _analysis_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def _key(self, patient_id: str, device_id: str) -> tuple[str, str]:
        return (patient_id, device_id)

    async def handle_transcript_chunk(self, payload: dict[str, Any]) -> None:
        text = (payload.get("text") or "").strip()
        if not text:
            return

        patient_id = payload.get("patient_id", self.patient_id)
        device_id = payload.get("device_id", self.device_id)
        key = self._key(patient_id, device_id)

        job: _AnalysisJob | None = None
        async with self._sessions_lock:
            session = self._sessions.get(key)
            if session is None:
                session = _SessionState(
                    conversation_id=self.repo.create_conversation(
                        patient_id=patient_id,
                        device_id=device_id,
                        language="bg",
                    )
                )
                self._sessions[key] = session

            self.repo.add_transcript_segment(
                conversation_id=session.conversation_id,
                patient_id=patient_id,
                ts_start_ms=int(payload.get("ts_start_ms", 0)),
                ts_end_ms=int(payload.get("ts_end_ms", 0)),
                text=text,
                stt_engine=payload.get("stt_engine", "unknown"),
                stt_confidence=float(payload.get("stt_confidence", 0.0)),
            )
            session.buffer.append(text)

            if len(session.buffer) >= self.flush_every_segments:
                job = self._build_job_and_reset(key, session, patient_id, device_id)

        if job is not None:
            asyncio.create_task(self._process_analysis_job(job))

    async def flush_session(self, patient_id: str, device_id: str) -> bool:
        key = self._key(patient_id, device_id)
        job: _AnalysisJob | None = None

        async with self._sessions_lock:
            session = self._sessions.get(key)
            if session is not None and session.buffer:
                job = self._build_job_and_reset(key, session, patient_id, device_id)

        if job is not None:
            asyncio.create_task(self._process_analysis_job(job))
            return True
        return False

    def _build_job_and_reset(
        self,
        key: tuple[str, str],
        session: _SessionState,
        patient_id: str,
        device_id: str,
    ) -> _AnalysisJob:
        transcript_text = " ".join(session.buffer)
        job = _AnalysisJob(
            conversation_id=session.conversation_id,
            patient_id=patient_id,
            device_id=device_id,
            transcript_text=transcript_text,
        )
        del self._sessions[key]
        return job

    async def _process_analysis_job(self, job: _AnalysisJob) -> None:
        async with self._analysis_lock:
            context = self.repo.get_memory_context(job.patient_id)
            analysis = self.ai_client.analyze_conversation(
                conversation_id=job.conversation_id,
                transcript_text=job.transcript_text,
                context=context,
            )

            self.repo.finalize_conversation(
                conversation_id=job.conversation_id,
                summary_text=analysis.summary_text,
                summary_confidence=analysis.urgency.confidence,
            )

            for person in analysis.people:
                self.repo.upsert_person_profile(
                    patient_id=job.patient_id,
                    name=person.name,
                    person_type=person.person_type,
                    relationship_to_patient=person.relationship_to_patient,
                    confidence=person.confidence,
                    notes="; ".join(person.source_evidence),
                )

            for reminder in analysis.reminders:
                self.repo.add_or_merge_reminder(
                    patient_id=job.patient_id,
                    source_conversation_id=job.conversation_id,
                    title=reminder.title,
                    details=reminder.details,
                    due_at=reminder.due_at,
                    recurrence_rule=reminder.recurrence_rule,
                    priority=reminder.priority,
                    confidence=reminder.confidence,
                )

            high_priority_titles = [r.title for r in analysis.reminders if r.priority == "high"]
            if high_priority_titles:
                await self.alert_engine.trigger(
                    alert_type="important_reminder_detected",
                    severity="warning",
                    title="Important reminder created",
                    message=", ".join(high_priority_titles[:3]),
                    payload={
                        "conversation_id": job.conversation_id,
                        "count": len(high_priority_titles),
                        "titles": high_priority_titles,
                    },
                    patient_id=job.patient_id,
                    device_id=job.device_id,
                )

            for note in analysis.memory_notes:
                if note.category == "preference":
                    fact_type = "patient_preference"
                elif note.category == "social_event":
                    fact_type = "event"
                else:
                    fact_type = "memory_note"
                self.repo.add_or_merge_fact(
                    patient_id=job.patient_id,
                    conversation_id=job.conversation_id,
                    fact_type=fact_type,
                    subject_ref="patient",
                    predicate=note.category,
                    object_value=note.note,
                    confidence=note.confidence,
                    source_evidence="; ".join(note.source_evidence),
                )

            important_notes = [n for n in analysis.memory_notes if n.category == "important_note"]
            if important_notes:
                await self.alert_engine.trigger(
                    alert_type="important_memory_note",
                    severity="info",
                    title="Important memory note captured",
                    message=important_notes[0].note[:120],
                    payload={
                        "conversation_id": job.conversation_id,
                        "count": len(important_notes),
                    },
                    patient_id=job.patient_id,
                    device_id=job.device_id,
                )

            for risk in analysis.safety_risks:
                self.repo.add_or_merge_fact(
                    patient_id=job.patient_id,
                    conversation_id=job.conversation_id,
                    fact_type="risk_note",
                    subject_ref="patient",
                    predicate=risk.risk_type,
                    object_value=risk.description,
                    confidence=risk.confidence,
                    source_evidence="; ".join(risk.source_evidence),
                )

            if analysis.urgency.level in {"warning", "critical"}:
                await self.alert_engine.trigger(
                    alert_type="ai_safety_signal",
                    severity=analysis.urgency.level,
                    title="AI safety signal detected",
                    message=analysis.urgency.reason,
                    payload={
                        "conversation_id": job.conversation_id,
                        "summary": analysis.summary_text,
                        "confidence": analysis.urgency.confidence,
                    },
                    patient_id=job.patient_id,
                    device_id=job.device_id,
                )


@dataclass
class SensorPipeline:
    repo: Repository
    alert_engine: AlertEngine
    geofence_engine: GeofenceEngine
    fall_detector: FallDetector
    patient_id: str
    device_id: str

    async def handle_gps(self, payload: dict[str, Any]) -> None:
        patient_id = payload.get("patient_id", self.patient_id)
        device_id = payload.get("device_id", self.device_id)
        zone = self.repo.get_active_zone(patient_id)
        lat = float(payload["lat"])
        lon = float(payload["lon"])
        speed = float(payload.get("speed_mps", 0.0))
        accuracy = float(payload.get("accuracy_m", 0.0))

        inside_zone = None
        zone_id = None
        if zone is not None:
            zone_id = zone["id"]
            inside_zone, distance_m, should_alert = self.geofence_engine.check(
                lat=lat,
                lon=lon,
                center_lat=float(zone["center_lat"]),
                center_lon=float(zone["center_lon"]),
                radius_m=float(zone["radius_m"]),
            )
            if should_alert:
                await self.alert_engine.trigger(
                    alert_type="geofence_breach",
                    severity="critical",
                    title="Patient left safe zone",
                    message=f"Distance from zone center: {distance_m:.1f}m",
                    payload={"lat": lat, "lon": lon, "zone_id": zone_id, "distance_m": distance_m},
                    patient_id=patient_id,
                    device_id=device_id,
                )

        self.repo.add_gps_event(
            patient_id=patient_id,
            device_id=device_id,
            lat=lat,
            lon=lon,
            speed_mps=speed,
            accuracy_m=accuracy,
            inside_zone=inside_zone,
            zone_id=zone_id,
        )

    async def handle_accelerometer(self, payload: dict[str, Any]) -> None:
        patient_id = payload.get("patient_id", self.patient_id)
        device_id = payload.get("device_id", self.device_id)
        ts = datetime.now(tz=timezone.utc)
        evt = self.fall_detector.update(
            ax=float(payload["ax"]),
            ay=float(payload["ay"]),
            az=float(payload["az"]),
            ts=ts,
        )
        if evt is None:
            return

        self.repo.add_fall_event(
            patient_id=patient_id,
            device_id=device_id,
            impact_g=evt.impact_g,
            orientation_delta=0.0,
            inactivity_sec=evt.inactivity_sec,
            confidence=evt.confidence,
            is_confirmed=False,
        )
        await self.alert_engine.trigger(
            alert_type="fall_detected",
            severity="critical",
            title="Potential fall detected",
            message=f"Impact {evt.impact_g:.2f}g with inactivity {evt.inactivity_sec}s",
            payload={"impact_g": evt.impact_g, "inactivity_sec": evt.inactivity_sec, "confidence": evt.confidence},
            patient_id=patient_id,
            device_id=device_id,
        )
