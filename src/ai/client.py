import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.ai.schemas.contracts import (
    ExtractedPerson,
    Incident,
    MemoryNote,
    Reminder,
    SafetyRisk,
    TranscriptAnalysisResult,
    Urgency,
)


NAME_PATTERN = re.compile(r"\b([A-ZА-Я][a-zа-я]{2,}|[A-ZА-Я][a-zа-я]+\s[A-ZА-Я][a-zа-я]+)\b")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")
TIME_PATTERN = re.compile(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
TIME_COLON_PATTERN = re.compile(r"(?:\b(?:at|в)\s*)?(\d{1,2}):(\d{2})\s*(am|pm)?\b", re.IGNORECASE)
MEET_PERSON_PATTERN = re.compile(r"\b(?:meet|see)\s+([a-zA-Z][a-zA-Z\-']{1,30})\b", re.IGNORECASE)
ADDRESS_PATTERN = re.compile(r"(?:адрес|address)\s+([^.!,?]+)", re.IGNORECASE)
DOCTOR_NAME_PATTERN = re.compile(
    r"(?:д-р\.?|др\.?|dr\.?|doctor)\s+([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)?)",
    re.IGNORECASE,
)
BIRTHDAY_HOST_PATTERN = re.compile(
    r"(?:рожден\s+ден\s+на|birthday\s+(?:party\s+)?(?:for|of))\s+([^.!,?]+?)(?:\s+на\s+адрес|\s+at\s+address|\s+в\s+\d{1,2}(?::\d{2})?|$)",
    re.IGNORECASE,
)

WEEKDAY_MAP = {
    "monday": 0,
    "mon": 0,
    "понеделник": 0,
    "tuesday": 1,
    "tue": 1,
    "вторник": 1,
    "wednesday": 2,
    "wed": 2,
    "сряда": 2,
    "thursday": 3,
    "thu": 3,
    "четвъртък": 3,
    "четвъртак": 3,
    "friday": 4,
    "fri": 4,
    "петък": 4,
    "petak": 4,
    "petyk": 4,
    "saturday": 5,
    "sat": 5,
    "saterday": 5,
    "satuday": 5,
    "събота": 5,
    "subota": 5,
    "sunday": 6,
    "sun": 6,
    "неделя": 6,
}

SPECIALTY_MAP = {
    "cardiologist": "cardiologist",
    "кардиолог": "cardiologist",
    "невролог": "neurologist",
    "neurologist": "neurologist",
    "endocrinologist": "endocrinologist",
    "ендокринолог": "endocrinologist",
    "psychiatrist": "psychiatrist",
    "психиатър": "psychiatrist",
    "therapist": "therapist",
    "терапевт": "therapist",
    "gp": "general_practitioner",
    "личен лекар": "general_practitioner",
}


@dataclass
class AIClient:
    """
    Local deterministic extraction engine for MVP.

    This version is more conversation-aware for reminders, especially medication plans.
    """

    def analyze_conversation(
        self,
        conversation_id: str,
        transcript_text: str,
        context: dict,
    ) -> TranscriptAnalysisResult:
        people = self._extract_people(transcript_text)
        reminders = self._extract_reminders(transcript_text)
        memory_notes = self._extract_memory_notes(transcript_text)
        safety_risks = self._extract_risks(transcript_text)
        incidents = self._extract_incidents(transcript_text)
        urgency = self._classify_urgency(safety_risks, incidents)

        summary_text = self._summary(transcript_text, people, reminders, memory_notes, safety_risks)

        if context.get("active_risks") and urgency.level == "info" and safety_risks:
            urgency = Urgency(level="warning", reason="Risk recurs in recent context", confidence=0.72)

        return TranscriptAnalysisResult(
            conversation_id=conversation_id,
            summary_text=summary_text,
            urgency=urgency,
            people=people,
            reminders=reminders,
            memory_notes=memory_notes,
            safety_risks=safety_risks,
            incidents=incidents,
        )

    def _split_sentences(self, text: str) -> list[str]:
        parts = [p.strip() for p in SENTENCE_SPLIT_PATTERN.split(text) if p.strip()]
        return parts or [text.strip()]

    def _extract_people(self, text: str) -> list[ExtractedPerson]:
        names = set()
        text_l = text.lower()
        blocked_names = {
            "the",
            "this",
            "that",
            "please",
            "today",
            "tomorrow",
            "doctor",
            "доктор",
            "dr",
            "др",
            "patient",
            "здрасти",
            "бабо",
            "утре",
            "днес",
        }
        for match in NAME_PATTERN.findall(text):
            token = match.strip()
            if token.lower() in blocked_names:
                continue
            names.add(token)

        doctor_name = self._extract_doctor_name(text)
        if doctor_name:
            names.add(doctor_name)

        result: list[ExtractedPerson] = []
        for name in sorted(names):
            relationship = "known_person"
            person_type = "other"

            if any(k in text_l for k in ["daughter", "son", "wife", "husband", "mother", "father"]):
                person_type = "family"
                relationship = "family"
            if any(k in text_l for k in ["caregiver", "nurse", "assistant"]):
                person_type = "caregiver"
                relationship = "caregiver"
            if any(k in text_l for k in ["doctor", "dr", "physician", "cardiologist", "neurologist", "доктор", "лекар"]):
                person_type = "medical"
                relationship = "doctor"

            result.append(
                ExtractedPerson(
                    name=name,
                    person_type=person_type,
                    relationship_to_patient=relationship,
                    confidence=0.72,
                    source_evidence=[text[:140]],
                )
            )
        return result[:8]

    def _extract_reminders(self, text: str) -> list[Reminder]:
        reminders: list[Reminder] = []
        sentences = self._split_sentences(text)

        for sentence in sentences:
            sentence_l = sentence.lower()

            # Explicit remember commands.
            if any(k in sentence_l for k in ["remember", "don't forget", "do not forget", "напомни", "не забравяй"]):
                reminders.append(
                    Reminder(
                        title="Remember important note",
                        details=sentence[:220],
                        due_at=None,
                        recurrence_rule=None,
                        priority="high" if any(k in sentence_l for k in ["important", "urgent", "спешно"]) else "medium",
                        confidence=0.8,
                        source_evidence=[sentence[:160]],
                    )
                )

            # Doctor visit / checkup intent (EN + BG), e.g. "трябва да отида на лекар в петък".
            doctor_visit = self._extract_doctor_visit_reminder(sentence)
            if doctor_visit is not None:
                reminders.append(doctor_visit)

            # Appointments.
            if any(k in sentence_l for k in ["appointment", "visit", "checkup", "clinic", "hospital", "преглед"]):
                due_at, recurrence = self._infer_schedule(sentence_l)
                reminders.append(
                    Reminder(
                        title="Medical appointment",
                        details=sentence[:220],
                        due_at=due_at,
                        recurrence_rule=recurrence,
                        priority="high",
                        confidence=0.78,
                        source_evidence=[sentence[:160]],
                    )
                )

            # Medication plans from conversational instructions.
            medication_reminder = self._extract_medication_reminder(sentence)
            if medication_reminder is not None:
                reminders.append(medication_reminder)

            # Doctor instruction that implies daily treatment even when "pill/medicine" is omitted.
            implied_treatment = self._extract_implied_doctor_treatment(sentence)
            if implied_treatment is not None:
                reminders.append(implied_treatment)

            # Meetings with people (e.g. "meet Lisa tomorrow").
            meeting_reminder = self._extract_meeting_reminder(sentence)
            if meeting_reminder is not None:
                reminders.append(meeting_reminder)

            social_event = self._extract_social_event_reminder(sentence)
            if social_event is not None:
                reminders.append(social_event)

            # Generic tasks.
            if any(k in sentence_l for k in ["call", "bring", "buy", "pick up", "обади", "купи", "донеси"]):
                due_at, recurrence = self._infer_schedule(sentence_l)
                reminders.append(
                    Reminder(
                        title="Follow-up task",
                        details=sentence[:220],
                        due_at=due_at,
                        recurrence_rule=recurrence,
                        priority="medium",
                        confidence=0.68,
                        source_evidence=[sentence[:160]],
                    )
                )

        deduped: dict[tuple[str, str, str, str], Reminder] = {}
        for reminder in reminders:
            key = (
                reminder.title.strip().lower(),
                reminder.details.strip().lower(),
                (reminder.due_at or "").strip().lower(),
                (reminder.recurrence_rule or "").strip().lower(),
            )
            current = deduped.get(key)
            if current is None or reminder.confidence > current.confidence:
                deduped[key] = reminder
        return list(deduped.values())

    def _extract_doctor_visit_reminder(self, sentence: str) -> Reminder | None:
        sentence_l = sentence.lower()

        doctor_terms = [
            "doctor",
            "dr",
            "д-р",
            "др",
            "physician",
            "доктор",
            "лекар",
            "лекаря",
            "личен лекар",
            "кардиолог",
            "невролог",
            "ендокринолог",
            "психиатър",
            "терапевт",
            "cardiologist",
            "neurologist",
            "endocrinologist",
            "psychiatrist",
            "therapist",
        ]
        has_doctor = any(t in sentence_l for t in doctor_terms)
        if not has_doctor:
            return None

        visit_terms = [
            "go to",
            "go see",
            "visit",
            "see the doctor",
            "appointment",
            "checkup",
            "clinic",
            "hospital",
            "преглед",
            "клиника",
            "болница",
            "отида на",
            "отивам на",
            "отидеш на",
            "трябва да отидеш",
            "да отида на",
            "посетя",
            "на лекар",
            "на доктор",
            "при лекар",
            "при доктор",
            "при кардиолог",
            "при невролог",
            "при ендокринолог",
            "при доктора",
            "при лекаря",
            "при д-р",
            "при др",
            "при dr",
            "при specialist",
        ]
        has_visit_intent = any(v in sentence_l for v in visit_terms)

        if not has_visit_intent:
            return None

        due_at, recurrence = self._infer_schedule(sentence_l, default_hour=10, default_minute=0)
        confidence = 0.88 if due_at is not None else 0.8

        doctor_name = self._extract_doctor_name(sentence)
        specialty = self._extract_specialty(sentence_l)

        title = "Medical appointment"
        if specialty and doctor_name:
            title = f"Medical appointment ({specialty}, Dr {doctor_name})"
        elif specialty:
            title = f"Medical appointment ({specialty})"
        elif doctor_name:
            title = f"Medical appointment (Dr {doctor_name})"

        details = sentence[:220]
        if doctor_name and doctor_name.lower() not in details.lower():
            details = f"{details} Doctor: {doctor_name}"[:220]

        return Reminder(
            title=title,
            details=details,
            due_at=due_at,
            recurrence_rule=recurrence,
            priority="high",
            confidence=confidence,
            source_evidence=[sentence[:160]],
        )

    def _extract_meeting_reminder(self, sentence: str) -> Reminder | None:
        sentence_l = sentence.lower()
        if not any(k in sentence_l for k in ["meet", "see", "meeting", "среща", "срещна", "ще видя", "видя се"]):
            return None

        due_at, recurrence = self._infer_schedule(sentence_l)
        if due_at is None and recurrence is None and not any(
            k in sentence_l for k in ["tomorrow", "tommorow", "tomorow", "утре", "today", "днес"]
        ):
            return None

        person_match = MEET_PERSON_PATTERN.search(sentence)
        person_name = person_match.group(1) if person_match else "person"

        return Reminder(
            title=f"Meet {person_name.capitalize()}",
            details=sentence[:220],
            due_at=due_at,
            recurrence_rule=recurrence,
            priority="medium",
            confidence=0.8,
            source_evidence=[sentence[:160]],
        )

    def _extract_social_event_reminder(self, sentence: str) -> Reminder | None:
        sentence_l = sentence.lower()
        is_party = any(k in sentence_l for k in ["party", "birthday", "birthday party", "рожден", "рожден ден", "парти", "купон"])
        is_invite = any(k in sentence_l for k in ["invited", "invite", "invitation", "поканен", "покани", "покана"])

        if not (is_party or is_invite):
            return None

        due_at, recurrence = self._infer_schedule(
            sentence_l,
            default_hour=18,
            default_minute=0,
            prefer_pm_for_ambiguous=True,
        )

        host = self._extract_birthday_host(sentence)
        address = self._extract_address(sentence)

        title = "Birthday party" if any(k in sentence_l for k in ["birthday", "рожден"]) else "Social event"
        if host:
            title = f"{title} ({host})"

        details = sentence[:220]
        if address and address.lower() not in details.lower():
            details = f"{details} Address: {address}"[:220]

        return Reminder(
            title=title,
            details=details,
            due_at=due_at,
            recurrence_rule=recurrence,
            priority="medium",
            confidence=0.84,
            source_evidence=[sentence[:160]],
        )

    def _extract_birthday_host(self, sentence: str) -> str | None:
        m = BIRTHDAY_HOST_PATTERN.search(sentence)
        if not m:
            return None
        host = m.group(1).strip(" .,")
        if not host:
            return None
        return host

    def _extract_doctor_name(self, sentence: str) -> str | None:
        m = DOCTOR_NAME_PATTERN.search(sentence)
        if not m:
            return None
        name = m.group(1).strip(" .,")
        if not name:
            return None
        return name

    def _extract_specialty(self, sentence_l: str) -> str | None:
        for key, value in SPECIALTY_MAP.items():
            if key in sentence_l:
                return value
        return None

    def _extract_address(self, sentence: str) -> str | None:
        m = ADDRESS_PATTERN.search(sentence)
        if not m:
            return None
        raw = m.group(1).strip()
        raw = re.sub(r"\s+в\s+\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?\s*$", "", raw, flags=re.IGNORECASE)
        cleaned = raw.strip(" .,")
        return cleaned or None

    def _extract_medication_reminder(self, sentence: str) -> Reminder | None:
        sentence_l = sentence.lower()
        medication_words = [
            "medicine",
            "medication",
            "pill",
            "pills",
            "peels",
            "tablet",
            "tablets",
            "dose",
            "хапче",
            "хапчета",
            "лекарство",
            "лекарства",
        ]
        action_words = [
            "take",
            "takes",
            "must take",
            "needs to take",
            "should take",
            "start taking",
            "взема",
            "пие",
            "трябва да",
        ]
        medical_context = ["doctor", "dr", "physician", "доктор", "лекар"]

        has_medication = any(w in sentence_l for w in medication_words)
        has_action = any(w in sentence_l for w in action_words)
        has_medical_context = any(w in sentence_l for w in medical_context)

        if not has_medication:
            return None
        if not (has_action or has_medical_context):
            return None

        recurrence = self._infer_medication_recurrence(sentence_l)
        due_at, schedule_recurrence = self._infer_schedule(sentence_l)

        if recurrence is None and schedule_recurrence:
            recurrence = schedule_recurrence
        if recurrence is None:
            recurrence = "FREQ=DAILY"

        details = sentence.strip()
        priority = "high" if has_medical_context else "medium"
        confidence = 0.9 if has_medical_context else 0.82

        return Reminder(
            title="Take medication",
            details=details[:220],
            due_at=due_at,
            recurrence_rule=recurrence,
            priority=priority,
            confidence=confidence,
            source_evidence=[details[:160]],
        )

    def _extract_implied_doctor_treatment(self, sentence: str) -> Reminder | None:
        sentence_l = sentence.lower()
        has_doctor = any(k in sentence_l for k in ["doctor", "dr", "physician", "доктор", "лекар"])
        has_take = any(k in sentence_l for k in ["take", "needs to take", "should take", "трябва да взема", "да пие"])
        has_daily_pattern = any(
            k in sentence_l
            for k in ["every day", "daily", "each day", "every morning", "in the morning", "сутрин", "всеки ден", "ежедневно"]
        )

        if not (has_doctor and has_take and has_daily_pattern):
            return None

        # If explicit medication reminder was already possible, do not duplicate with implied one.
        if any(k in sentence_l for k in ["pill", "pills", "peels", "tablet", "medicine", "medication", "хапче", "лекарство"]):
            return None

        recurrence = self._infer_medication_recurrence(sentence_l) or "FREQ=DAILY"
        due_at, _ = self._infer_schedule(sentence_l)

        return Reminder(
            title="Take prescribed treatment",
            details=sentence[:220],
            due_at=due_at,
            recurrence_rule=recurrence,
            priority="high",
            confidence=0.76,
            source_evidence=[sentence[:160]],
        )

    def _infer_medication_recurrence(self, sentence_l: str) -> str | None:
        if any(k in sentence_l for k in ["twice a day", "2 times a day", "два пъти на ден"]):
            return "FREQ=DAILY;BYHOUR=08,20;BYMINUTE=00"
        if any(k in sentence_l for k in ["three times a day", "3 times a day", "три пъти на ден"]):
            return "FREQ=DAILY;BYHOUR=08,14,20;BYMINUTE=00"
        if any(k in sentence_l for k in ["every morning", "in the morning", "сутрин"]):
            return "FREQ=DAILY;BYHOUR=08;BYMINUTE=00"
        if any(k in sentence_l for k in ["every evening", "in the evening", "вечер"]):
            return "FREQ=DAILY;BYHOUR=20;BYMINUTE=00"
        if any(k in sentence_l for k in ["every night", "nightly", "нощем"]):
            return "FREQ=DAILY;BYHOUR=22;BYMINUTE=00"
        if any(k in sentence_l for k in ["daily", "every day", "each day", "ежедневно", "всеки ден"]):
            return "FREQ=DAILY"
        return None

    def _infer_schedule(
        self,
        sentence_l: str,
        default_hour: int = 9,
        default_minute: int = 0,
        prefer_pm_for_ambiguous: bool = False,
    ) -> tuple[str | None, str | None]:
        now = datetime.now(tz=timezone.utc)
        due_at: str | None = None
        recurrence: str | None = None

        if any(k in sentence_l for k in ["daily", "every day", "each day", "ежедневно", "всеки ден"]):
            recurrence = "FREQ=DAILY"
        elif any(k in sentence_l for k in ["weekly", "every week", "седмично"]):
            recurrence = "FREQ=WEEKLY"

        hour, minute, explicit_meridiem = self._extract_time(sentence_l)
        if (
            hour is not None
            and prefer_pm_for_ambiguous
            and not explicit_meridiem
            and 1 <= hour <= 7
            and not any(k in sentence_l for k in ["morning", "сутрин"])
        ):
            hour += 12

        if hour is not None:
            if recurrence == "FREQ=DAILY":
                recurrence = f"FREQ=DAILY;BYHOUR={hour};BYMINUTE={minute}"
            due_at = self._next_occurrence_iso(hour=hour, minute=minute)

        weekday_idx = self._extract_weekday(sentence_l)
        if weekday_idx is not None:
            use_hour = hour if hour is not None else default_hour
            use_minute = minute if hour is not None else default_minute
            due_at = self._next_weekday_occurrence_iso(weekday_idx, use_hour, use_minute)

        if any(k in sentence_l for k in ["tomorrow", "tommorow", "tomorow", "утре"]):
            base = now + timedelta(days=1)
            if hour is None:
                base = base.replace(hour=default_hour, minute=default_minute, second=0, microsecond=0)
            else:
                base = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            due_at = base.isoformat()

        if any(k in sentence_l for k in ["today", "днес"]) and due_at is None:
            base = now + timedelta(hours=1)
            due_at = base.replace(second=0, microsecond=0).isoformat()

        return due_at, recurrence

    def _extract_weekday(self, sentence_l: str) -> int | None:
        for token, weekday in WEEKDAY_MAP.items():
            if token in sentence_l:
                return weekday
        return None

    def _next_weekday_occurrence_iso(self, weekday: int, hour: int, minute: int) -> str:
        now = datetime.now(tz=timezone.utc)
        days_ahead = (weekday - now.weekday()) % 7
        if days_ahead == 0:
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                days_ahead = 7
        target = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        return target.isoformat()

    def _extract_time(self, sentence_l: str) -> tuple[int | None, int, bool]:
        colon_matches = list(TIME_COLON_PATTERN.finditer(sentence_l))
        match = colon_matches[-1] if colon_matches else None

        if not match:
            # Fallback for hour-only expressions like "at 5 pm".
            candidates = list(TIME_PATTERN.finditer(sentence_l))
            if candidates:
                scored: list[tuple[int, re.Match[str]]] = []
                for m in candidates:
                    start = m.start()
                    prefix = sentence_l[max(0, start - 8) : start]
                    score = 0
                    if m.group(3):
                        score += 3
                    if "at" in prefix or "в" in prefix:
                        score += 2
                    if m.group(2):
                        score += 2
                    if "адрес" in sentence_l[max(0, start - 12) : start]:
                        score -= 3
                    scored.append((score, m))
                scored.sort(key=lambda x: x[0])
                match = scored[-1][1]

        if not match:
            if "morning" in sentence_l or "сутрин" in sentence_l:
                return 8, 0, False
            if "evening" in sentence_l or "вечер" in sentence_l:
                return 20, 0, False
            if "night" in sentence_l or "нощ" in sentence_l:
                return 22, 0, False
            return None, 0, False

        hour = int(match.group(1))
        minute = int(match.group(2) or "0")
        ampm = (match.group(3) or "").lower()
        explicit_meridiem = bool(ampm)

        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0

        if hour > 23 or minute > 59:
            return None, 0, explicit_meridiem
        return hour, minute, explicit_meridiem

    def _next_occurrence_iso(self, hour: int, minute: int) -> str:
        now = datetime.now(tz=timezone.utc)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target.isoformat()

    def _extract_memory_notes(self, text: str) -> list[MemoryNote]:
        text_l = text.lower()
        notes: list[MemoryNote] = []
        for sentence in self._split_sentences(text):
            sentence_l = sentence.lower()

            if any(k in sentence_l for k in ["remember", "don't forget", "do not forget", "не забравяй"]):
                notes.append(
                    MemoryNote(
                        note=sentence[:220],
                        category="important_note",
                        confidence=0.8,
                        source_evidence=[sentence[:160]],
                    )
                )

            if any(k in sentence_l for k in ["i like", "i prefer", "my favorite", "харесвам", "предпочитам"]):
                notes.append(
                    MemoryNote(
                        note=sentence[:220],
                        category="preference",
                        confidence=0.76,
                        source_evidence=[sentence[:160]],
                    )
                )

            if any(k in sentence_l for k in ["my daughter", "my son", "my wife", "my husband", "дъщеря", "син"]):
                notes.append(
                    MemoryNote(
                        note=sentence[:220],
                        category="family_detail",
                        confidence=0.74,
                        source_evidence=[sentence[:160]],
                    )
                )

            if any(
                k in sentence_l
                for k in [
                    "birthday",
                    "party",
                    "invited",
                    "meeting",
                    "meet",
                    "рожден",
                    "парти",
                    "покан",
                    "среща",
                ]
            ):
                notes.append(
                    MemoryNote(
                        note=sentence[:220],
                        category="social_event",
                        confidence=0.78,
                        source_evidence=[sentence[:160]],
                    )
                )

            if any(k in sentence_l for k in ["i have a dog", "i have dog", "my dog", "i have a cat", "my cat", "имам куче", "имам котка"]):
                notes.append(
                    MemoryNote(
                        note=sentence[:220],
                        category="pet_detail",
                        confidence=0.8,
                        source_evidence=[sentence[:160]],
                    )
                )

        deduped: dict[tuple[str, str], MemoryNote] = {}
        for note in notes:
            key = (note.category.lower(), note.note.strip().lower())
            current = deduped.get(key)
            if current is None or note.confidence > current.confidence:
                deduped[key] = note
        return list(deduped.values())

    def _extract_risks(self, text: str) -> list[SafetyRisk]:
        text_l = text.lower()
        risks: list[SafetyRisk] = []

        if any(k in text_l for k in ["lost", "where am i", "confused", "don't know where", "объркан", "изгубен"]):
            risks.append(
                SafetyRisk(
                    risk_type="disorientation",
                    severity="high",
                    description="Possible disorientation detected in speech.",
                    confidence=0.82,
                    source_evidence=[text[:180]],
                )
            )

        if any(
            k in text_l
            for k in [
                "forgot medicine",
                "did i take",
                "not sure if i took",
                "missed dose",
                "did i already take",
                "double dose",
                "forgot my pill",
                "забравих",
                "дали взех",
            ]
        ):
            risks.append(
                SafetyRisk(
                    risk_type="medication_confusion",
                    severity="high",
                    description="Medication uncertainty mentioned.",
                    confidence=0.84,
                    source_evidence=[text[:180]],
                )
            )

        if "fell" in text_l or "i fell" in text_l or "паднах" in text_l:
            risks.append(
                SafetyRisk(
                    risk_type="fall_risk",
                    severity="critical",
                    description="Speech indicates a possible fall event.",
                    confidence=0.9,
                    source_evidence=[text[:180]],
                )
            )

        return risks

    def _extract_incidents(self, text: str) -> list[Incident]:
        incidents: list[Incident] = []
        text_l = text.lower()

        if "fell" in text_l or "паднах" in text_l:
            incidents.append(
                Incident(
                    incident_type="fall_suspected",
                    description="Conversation includes explicit mention of a fall.",
                    severity="critical",
                    confidence=0.88,
                )
            )

        if "left home" in text_l or "outside" in text_l or "излязъл" in text_l:
            incidents.append(
                Incident(
                    incident_type="wandering_suspected",
                    description="Conversation indicates patient may be outside safe area.",
                    severity="high",
                    confidence=0.76,
                )
            )
        return incidents

    def _classify_urgency(self, risks: list[SafetyRisk], incidents: list[Incident]) -> Urgency:
        if any(r.severity == "critical" for r in risks) or any(i.severity == "critical" for i in incidents):
            return Urgency(level="critical", reason="Critical safety signal in transcript", confidence=0.9)
        if risks or incidents:
            return Urgency(level="warning", reason="Potential safety-relevant content", confidence=0.78)
        return Urgency(level="info", reason="No immediate safety issue", confidence=0.72)

    def _summary(
        self,
        text: str,
        people: list[ExtractedPerson],
        reminders: list[Reminder],
        memory_notes: list[MemoryNote],
        safety_risks: list[SafetyRisk],
    ) -> str:
        people_part = f"People detected: {', '.join(p.name for p in people)}. " if people else ""
        reminders_part = f"Reminders: {len(reminders)}. " if reminders else ""
        notes_part = f"Memory notes: {len(memory_notes)}. " if memory_notes else ""
        risks_part = f"Risks: {', '.join(r.risk_type for r in safety_risks)}. " if safety_risks else ""
        transcript_part = text[:200]
        return f"{people_part}{reminders_part}{notes_part}{risks_part}Transcript: {transcript_part}".strip()
