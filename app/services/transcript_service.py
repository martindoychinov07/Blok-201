import sqlite3
import re

from app.schemas import AnalysisResult, Appointment, Person, Reminder, TranscriptIn
from app.services.analysis_webhook import AnalysisWebhookPublisher
from app.services.fallback_extractor import FallbackExtractor
from app.services.gemini_service import GeminiServiceError
from app.services.gemini_service import GeminiService
from app.services.memory_service import MemoryService


class TranscriptService:
    def __init__(
        self,
        gemini_service: GeminiService,
        memory_service: MemoryService,
        fallback_extractor: FallbackExtractor,
        fallback_enabled: bool,
        analysis_webhook: AnalysisWebhookPublisher | None = None,
    ):
        self.gemini_service = gemini_service
        self.memory_service = memory_service
        self.fallback_extractor = fallback_extractor
        self.fallback_enabled = fallback_enabled
        self.analysis_webhook = analysis_webhook

    def analyze_and_persist(self, payload: TranscriptIn) -> tuple[int, AnalysisResult, dict[str, int], str, str | None]:
        transcript_id = self.memory_service.save_raw_transcript(payload)
        source = "gemini"
        warning: str | None = None

        try:
            analysis = self.gemini_service.analyze_transcript(payload.text)
        except GeminiServiceError as exc:
            if not self.fallback_enabled:
                raise
            analysis = self.fallback_extractor.analyze(payload.text)
            source = "fallback"
            warning = f"Gemini unavailable, used fallback extractor: {self._compact_error(exc)}"

        analysis = self._enrich_analysis(analysis, payload.text)

        try:
            saved = self.memory_service.persist_analysis(
                patient_id=payload.patient_id,
                transcript_id=transcript_id,
                analysis=analysis,
            )
        except sqlite3.Error:
            raise

        if self.analysis_webhook is not None:
            bridge_warning = self.analysis_webhook.publish_analysis_event(
                transcript_id=transcript_id,
                payload=payload,
                analysis=analysis,
                saved=saved,
                source=source,
                warning=warning,
            )
            if bridge_warning:
                warning = f"{warning} | {bridge_warning}" if warning else bridge_warning

        return transcript_id, analysis, saved, source, warning

    def _enrich_analysis(self, analysis: AnalysisResult, transcript_text: str) -> AnalysisResult:
        people = list(analysis.people)
        reminders = list(analysis.reminders)
        appointments = list(analysis.appointments)
        medications = list(analysis.medications)
        safety_notes = list(analysis.safety_notes)
        important_facts = list(analysis.important_facts)

        derived_reminders = self._derive_reminders_from_transcript(transcript_text)
        derived_appointments = self._derive_appointments_from_transcript(transcript_text)

        for item in derived_appointments:
            if not self._has_appointment(appointments, item):
                appointments.append(item)

        for item in derived_reminders:
            if not self._has_reminder(reminders, item):
                reminders.append(item)

        # Keep behavior closer to previous system: appointments imply actionable reminders.
        for appointment in appointments:
            if appointment.doctor and not self._has_person(people, appointment.doctor):
                people.append(Person(name=appointment.doctor, relationship="doctor"))

            if not self._has_appointment_reminder(reminders, appointment.title, appointment.time_text):
                reminder_text = f"Attend {appointment.title}"
                if appointment.doctor:
                    reminder_text += f" with {appointment.doctor}"
                reminders.append(
                    Reminder(
                        type="appointment",
                        text=reminder_text,
                        time_text=appointment.time_text,
                    )
                )

            fact = self._appointment_fact_text(appointment.title, appointment.doctor, appointment.time_text)
            if fact and fact not in important_facts:
                important_facts.append(fact)

        # If there are reminders but no facts, keep at least one useful fact.
        if reminders and not important_facts:
            for reminder in reminders[:3]:
                fact = f"Reminder: {reminder.text}" + (f" ({reminder.time_text})" if reminder.time_text else "")
                if fact not in important_facts:
                    important_facts.append(fact)

        if transcript_text and len(important_facts) < 8:
            for reminder in reminders:
                fact = f"Task: {reminder.text}" + (f" ({reminder.time_text})" if reminder.time_text else "")
                if fact not in important_facts:
                    important_facts.append(fact)
                if len(important_facts) >= 8:
                    break

        reminders = self._drop_overall_transcript_reminders(reminders, transcript_text)

        return AnalysisResult(
            people=self._dedup_people(people),
            appointments=appointments,
            reminders=self._dedup_reminders(reminders),
            medications=medications,
            safety_notes=safety_notes,
            important_facts=important_facts,
        )

    def _has_person(self, people: list[Person], name: str) -> bool:
        target = name.strip().lower()
        return any(p.name.strip().lower() == target for p in people)

    def _has_appointment_reminder(self, reminders: list[Reminder], title: str, time_text: str | None) -> bool:
        title_l = title.strip().lower()
        time_l = (time_text or "").strip().lower()
        for reminder in reminders:
            if reminder.type != "appointment":
                continue
            txt = reminder.text.strip().lower()
            if title_l in txt and ((reminder.time_text or "").strip().lower() == time_l):
                return True
        return False

    def _has_reminder(self, reminders: list[Reminder], candidate: Reminder) -> bool:
        key = (
            candidate.type.strip().lower(),
            candidate.text.strip().lower(),
            (candidate.time_text or "").strip().lower(),
        )
        for reminder in reminders:
            current = (
                reminder.type.strip().lower(),
                reminder.text.strip().lower(),
                (reminder.time_text or "").strip().lower(),
            )
            if current == key:
                return True
        return False

    def _has_appointment(self, appointments: list[Appointment], candidate: Appointment) -> bool:
        c_title = candidate.title.strip().lower()
        c_doctor = self._normalize_doctor_name(candidate.doctor)
        c_time = self._normalize_time_text(candidate.time_text)
        for appointment in appointments:
            a_title = appointment.title.strip().lower()
            a_doctor = self._normalize_doctor_name(appointment.doctor)
            a_time = self._normalize_time_text(appointment.time_text)

            if (a_title, a_doctor, a_time) == (c_title, c_doctor, c_time):
                return True

            # Same doctor + same time usually means same appointment, even if title wording differs.
            if c_doctor and c_time and a_doctor == c_doctor and a_time == c_time:
                return True

            # Tolerate small time phrasing variations: "tomorrow at 3 pm" vs "tomorrow 3 pm".
            if c_doctor and a_doctor == c_doctor and c_time and a_time and (c_time in a_time or a_time in c_time):
                return True

            # Same title + same time is also treated as duplicate.
            if c_title and c_time and a_title == c_title and a_time == c_time:
                return True
        return False

    def _normalize_doctor_name(self, value: str | None) -> str:
        if not value:
            return ""
        normalized = value.strip().lower()
        normalized = re.sub(r"^(dr\.?|doctor|д-р\.?|др\.?|доктор)\s+", "", normalized)
        normalized = re.sub(r"[.,]+$", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _normalize_time_text(self, value: str | None) -> str:
        if not value:
            return ""
        normalized = value.strip().lower()
        normalized = normalized.replace(" at ", " ").replace(" в ", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _derive_reminders_from_transcript(self, text: str) -> list[Reminder]:
        reminders: list[Reminder] = []
        for clause in self._split_action_clauses(text):
            lower = clause.lower()
            if not self._is_actionable_clause(lower):
                continue

            reminder_type = "task"
            if any(k in lower for k in ["рожден", "парти", "birthday", "party", "покан"]):
                reminder_type = "event"
            elif any(k in lower for k in ["хапч", "лекарств", "pill", "medicine", "medication", "доза"]):
                reminder_type = "medication"
            elif any(k in lower for k in ["обади", "позвъни", "call", "phone"]):
                reminder_type = "call"
            elif any(k in lower for k in ["преглед", "доктор", "лекар", "клиника", "hospital", "clinic", "appointment"]):
                reminder_type = "appointment"

            reminders.append(
                Reminder(
                    type=reminder_type,
                    text=clause[:220],
                    time_text=self._extract_time_text(clause),
                )
            )
        return reminders

    def _derive_appointments_from_transcript(self, text: str) -> list[Appointment]:
        out: list[Appointment] = []
        for clause in self._split_action_clauses(text):
            lower = clause.lower()
            if not any(
                k in lower
                for k in [
                    "преглед",
                    "доктор",
                    "лекар",
                    "кардиолог",
                    "невролог",
                    "клиника",
                    "болница",
                    "appointment",
                    "doctor",
                    "clinic",
                    "hospital",
                    "cardiologist",
                    "neurologist",
                ]
            ):
                continue

            title = "Medical appointment"
            if "кардиолог" in lower or "cardiologist" in lower:
                title = "Cardiology appointment"
            elif "невролог" in lower or "neurologist" in lower:
                title = "Neurology appointment"
            elif "лаборатор" in lower or "laboratory" in lower:
                title = "Laboratory tests"

            doctor = self._extract_doctor_name(clause)
            out.append(
                Appointment(
                    title=title,
                    doctor=doctor,
                    time_text=self._extract_time_text(clause),
                )
            )
        return out

    def _extract_doctor_name(self, clause: str) -> str | None:
        match = re.search(r"(?:д-р\.?|др\.?|dr\.?|doctor)\s+([A-ZА-Я][a-zа-я]+)", clause, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1)

    def _extract_time_text(self, clause: str) -> str | None:
        day = re.search(
            r"\b(утре|днес|понеделник|вторник|сряда|четвъртък|петък|събота|неделя|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            clause,
            flags=re.IGNORECASE,
        )
        time = re.search(r"\b\d{1,2}(?::\d{2})?\b\s*(?:am|pm)?", clause, flags=re.IGNORECASE)
        if day and time:
            return f"{day.group(1)} at {time.group(0)}"
        if day:
            return day.group(1)
        if time:
            return time.group(0)
        return None

    def _is_actionable_clause(self, lower_clause: str) -> bool:
        return any(
            token in lower_clause
            for token in [
                "трябва",
                "имаш",
                "покан",
                "срещ",
                "преглед",
                "обади",
                "купи",
                "минеш",
                "взим",
                "take",
                "need to",
                "have to",
                "appointment",
                "meet",
                "call",
                "buy",
                "visit",
            ]
        )

    def _split_action_clauses(self, text: str) -> list[str]:
        if not text.strip():
            return []

        marker = "__ABBR_DOT__"
        protected = re.sub(
            r"\b(?:dr|doctor|д-р|др|доктор)\.\s+",
            lambda m: m.group(0).replace(".", marker),
            text,
            flags=re.IGNORECASE,
        )

        first = [x.strip().replace(marker, ".") for x in re.split(r"(?<=[.!?])\s+|\n+", protected) if x.strip()]
        clauses: list[str] = []
        for sentence in first:
            parts = [x.strip() for x in re.split(r",\s*(?:а|и после|after that|then)\s+", sentence, flags=re.IGNORECASE) if x.strip()]
            clauses.extend(parts)
        return clauses

    def _appointment_fact_text(self, title: str, doctor: str | None, time_text: str | None) -> str:
        base = f"Appointment: {title}"
        if doctor:
            base += f" with {doctor}"
        if time_text:
            base += f" at {time_text}"
        return base

    def _dedup_people(self, people: list[Person]) -> list[Person]:
        out: list[Person] = []
        seen: set[tuple[str, str]] = set()
        for person in people:
            key = (person.name.strip().lower(), (person.relationship or "").strip().lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(person)
        return out

    def _dedup_reminders(self, reminders: list[Reminder]) -> list[Reminder]:
        out: list[Reminder] = []
        seen: set[tuple[str, str, str]] = set()
        for reminder in reminders:
            key = (
                reminder.type.strip().lower(),
                reminder.text.strip().lower(),
                (reminder.time_text or "").strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(reminder)
        return out

    def _drop_overall_transcript_reminders(self, reminders: list[Reminder], transcript_text: str) -> list[Reminder]:
        if len(reminders) < 2 or not transcript_text.strip():
            return reminders

        transcript_norm = self._normalize_free_text(transcript_text)
        if not transcript_norm:
            return reminders

        broad_indexes: set[int] = set()
        for index, reminder in enumerate(reminders):
            text_norm = self._normalize_free_text(reminder.text)
            if not text_norm:
                continue

            coverage = len(text_norm) / max(1, len(transcript_norm))
            matches_transcript = (
                text_norm == transcript_norm
                or text_norm in transcript_norm
                or transcript_norm in text_norm
            )
            has_many_actions = self._count_action_markers(text_norm) >= 2
            if matches_transcript and coverage >= 0.55 and has_many_actions:
                broad_indexes.add(index)

        if not broad_indexes:
            return reminders

        if len(reminders) - len(broad_indexes) < 1:
            return reminders

        return [reminder for index, reminder in enumerate(reminders) if index not in broad_indexes]

    def _normalize_free_text(self, text: str) -> str:
        normalized = re.sub(r"[\W_]+", " ", text.lower())
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _count_action_markers(self, text: str) -> int:
        markers = [
            "трябва",
            "имаш",
            "преглед",
            "срещ",
            "обади",
            "купи",
            "взим",
            "take",
            "need to",
            "have to",
            "appointment",
            "call",
            "buy",
            "visit",
            "then",
            "after that",
            "and",
            "и",
            "а",
        ]
        return sum(1 for marker in markers if marker in text)

    def _compact_error(self, exc: Exception) -> str:
        msg = str(exc).strip().replace("\n", " ")
        if "RESOURCE_EXHAUSTED" in msg:
            return "quota exhausted (RESOURCE_EXHAUSTED)"
        if len(msg) > 180:
            return msg[:177] + "..."
        return msg
