import re
from dataclasses import dataclass

from app.schemas import AnalysisResult, Appointment, Person, Reminder


NAME_PATTERN = re.compile(r"\b([A-ZА-Я][a-zа-я]{2,}|[A-ZА-Я][a-zа-я]+\s+[A-ZА-Я][a-zа-я]+)\b")


@dataclass
class FallbackExtractor:
    """Deterministic fallback extractor when Gemini is unavailable."""

    def analyze(self, text: str) -> AnalysisResult:
        text_l = text.lower()

        people = self._extract_people(text)
        appointments = self._extract_appointments(text)
        reminders = self._extract_reminders(text)
        meds = self._extract_medications(text_l)
        safety = self._extract_safety_notes(text_l)
        facts = self._extract_facts(text)

        return AnalysisResult(
            people=people,
            appointments=appointments,
            reminders=reminders,
            medications=meds,
            safety_notes=safety,
            important_facts=facts,
        )

    def _extract_people(self, text: str) -> list[Person]:
        people: list[Person] = []
        seen: set[str] = set()
        for match in NAME_PATTERN.findall(text):
            name = match.strip()
            lowered = name.lower()
            if lowered in {"tomorrow", "today", "doctor", "доктор", "лекар"}:
                continue
            if lowered in seen:
                continue
            seen.add(lowered)
            people.append(Person(name=name, relationship=None))
        return people[:8]

    def _extract_appointments(self, text: str) -> list[Appointment]:
        text_l = text.lower()
        items: list[Appointment] = []

        if any(k in text_l for k in ["doctor", "dr", "appointment", "clinic", "hospital", "доктор", "лекар", "преглед"]):
            doctor = None
            m = re.search(r"(?:dr\.?|doctor|д-р\.?|др\.?|доктор)\s+([A-ZА-Я][a-zа-я]+)", text, re.IGNORECASE)
            if m:
                doctor = m.group(1)

            time_text = self._extract_time_text(text)
            items.append(Appointment(title="Medical appointment", doctor=doctor, time_text=time_text))

        return items

    def _extract_reminders(self, text: str) -> list[Reminder]:
        text_l = text.lower()
        reminders: list[Reminder] = []

        if any(k in text_l for k in ["tomorrow", "tommorow", "утре", "today", "днес", "friday", "петък", "saturday", "събота"]):
            reminders.append(
                Reminder(
                    type="time_task",
                    text=text.strip()[:220],
                    time_text=self._extract_time_text(text),
                )
            )

        if any(k in text_l for k in ["pill", "pills", "medicine", "medication", "tablet", "dose", "meds", "хапче", "лекарство"]):
            reminders.append(
                Reminder(
                    type="medication",
                    text="Take medication as discussed",
                    time_text=self._extract_time_text(text),
                )
            )

        if any(k in text_l for k in ["birthday", "party", "рожден", "парти"]):
            reminders.append(
                Reminder(
                    type="event",
                    text="Attend social event",
                    time_text=self._extract_time_text(text),
                )
            )

        dedup: dict[tuple[str, str, str | None], Reminder] = {}
        for r in reminders:
            key = (r.type, r.text.lower(), r.time_text)
            dedup[key] = r
        return list(dedup.values())

    def _extract_medications(self, text_l: str) -> list[str]:
        meds: list[str] = []
        if "aspirin" in text_l:
            meds.append("Aspirin")
        if "metformin" in text_l:
            meds.append("Metformin")
        if any(k in text_l for k in ["pill", "medicine", "лекарство", "хапче"]) and not meds:
            meds.append("Medication mentioned")
        return meds

    def _extract_safety_notes(self, text_l: str) -> list[str]:
        notes: list[str] = []
        if any(k in text_l for k in ["confused", "disoriented", "объркан", "изгубен"]):
            notes.append("Possible confusion/disorientation")
        if any(k in text_l for k in ["fell", "fall", "паднах"]):
            notes.append("Possible fall mentioned")
        return notes

    def _extract_facts(self, text: str) -> list[str]:
        out: list[str] = []
        if text.strip():
            out.append(text.strip()[:220])
        return out[:3]

    def _extract_time_text(self, text: str) -> str | None:
        day_and_time = re.search(
            r"((?:tomorrow|tommorow|today|утре|днес|friday|saturday|sunday|monday|tuesday|wednesday|thursday|петък|събота|неделя|понеделник|вторник|сряда|четвъртък)\s*(?:at|от|в)?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            text,
            re.IGNORECASE,
        )
        if day_and_time:
            return day_and_time.group(1).strip()

        day_only = re.search(
            r"(tomorrow|tommorow|today|утре|днес|friday|saturday|sunday|monday|tuesday|wednesday|thursday|петък|събота|неделя|понеделник|вторник|сряда|четвъртък)",
            text,
            re.IGNORECASE,
        )
        if day_only:
            return day_only.group(1)

        time_only = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", text, re.IGNORECASE)
        if time_only:
            return time_only.group(1).strip()

        bg_from_time = re.search(r"(от\s*\d{1,2}:\d{2})", text, re.IGNORECASE)
        if bg_from_time:
            return bg_from_time.group(1).strip()

        simple_time = re.search(r"(в\s*\d{1,2}:\d{2})", text, re.IGNORECASE)
        if simple_time:
            return simple_time.group(1).strip()

        m = re.search(r"(\d{1,2}:\d{2})", text)
        if m:
            return m.group(1)

        m2 = re.search(r"(\d{1,2}\s*(?:am|pm))", text, re.IGNORECASE)
        if m2:
            return m2.group(1).strip()

        m3 = re.search(r"(tomorrow|tommorow|today|утре|днес|friday|saturday|sunday|петък|събота|неделя)", text, re.IGNORECASE)
        if m3:
            return m3.group(1)

        # nothing found
        return None
