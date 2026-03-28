from src.ai.client import AIClient
from datetime import datetime


def test_ai_client_returns_structured_result() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-1",
        transcript_text="Maria said tomorrow we have a doctor appointment and I forgot my medicine.",
        context={},
    )

    assert result.conversation_id == "conv-1"
    assert result.summary_text
    assert result.urgency.level in {"info", "warning", "critical"}
    assert isinstance(result.people, list)
    assert isinstance(result.reminders, list)
    assert isinstance(result.memory_notes, list)
    assert isinstance(result.safety_risks, list)


def test_ai_client_extracts_memory_note_from_remember_phrase() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-2",
        transcript_text="Please remember that I like tea in the morning.",
        context={},
    )

    assert len(result.memory_notes) >= 1
    assert any(note.category in {"important_note", "preference"} for note in result.memory_notes)


def test_ai_client_creates_daily_medication_reminder_from_doctor_instruction() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-3",
        transcript_text="The doctor said the patient needs to take pills every day in the morning.",
        context={},
    )

    med = [r for r in result.reminders if r.title == "Take medication"]
    assert med
    assert med[0].recurrence_rule is not None
    assert "FREQ=DAILY" in med[0].recurrence_rule

    risks = [r for r in result.safety_risks if r.risk_type == "medication_confusion"]
    assert not risks


def test_ai_client_creates_implied_daily_treatment_when_doctor_instruction_has_no_pill_word() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-4",
        transcript_text="The doctor said I need to take every day in the morning.",
        context={},
    )

    reminders = [r for r in result.reminders if r.title == "Take prescribed treatment"]
    assert reminders
    assert reminders[0].recurrence_rule is not None
    assert "FREQ=DAILY" in reminders[0].recurrence_rule


def test_ai_client_creates_meeting_reminder_with_tommorow_typo() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-5",
        transcript_text="I have to meet lisa tommorow.",
        context={},
    )

    reminders = [r for r in result.reminders if r.title.lower().startswith("meet ")]
    assert reminders
    assert reminders[0].due_at is not None


def test_ai_client_extracts_pet_memory_note() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-6",
        transcript_text="I have a dog named Rex.",
        context={},
    )

    pet_notes = [n for n in result.memory_notes if n.category == "pet_detail"]
    assert pet_notes


def test_ai_client_creates_birthday_party_event_reminder() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-7",
        transcript_text="I am invited to a birthday party on saturday.",
        context={},
    )

    event_reminders = [r for r in result.reminders if r.title in {"Birthday party", "Social event"}]
    assert event_reminders
    assert event_reminders[0].due_at is not None

    social_notes = [n for n in result.memory_notes if n.category == "social_event"]
    assert social_notes


def test_ai_client_handles_bulgarian_social_event() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-8",
        transcript_text="Поканен съм на рожден ден в събота вечер.",
        context={},
    )

    assert any(r.title in {"Birthday party", "Social event"} for r in result.reminders)
    assert any(n.category == "social_event" for n in result.memory_notes)

    birthday = next((r for r in result.reminders if r.title == "Birthday party"), None)
    assert birthday is not None
    assert birthday.due_at is not None


def test_ai_client_handles_bulgarian_doctor_visit_on_friday() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-9",
        transcript_text="Трябва да отида на лекар в петък.",
        context={},
    )

    med_appt = [r for r in result.reminders if r.title.startswith("Medical appointment")]
    assert med_appt
    assert med_appt[0].due_at is not None


def test_ai_client_handles_bulgarian_doctor_clinic_with_time() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-11",
        transcript_text="Утре трябва да отидеш на доктор в клиника 24 от 12:00.",
        context={},
    )

    med_appt = [r for r in result.reminders if r.title.startswith("Medical appointment")]
    assert med_appt
    assert med_appt[0].due_at is not None

    dt = datetime.fromisoformat(med_appt[0].due_at)
    assert dt.hour == 12


def test_ai_client_handles_dr_ivanov_name() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-12",
        transcript_text="Утре в 14:30 трябва да отида при д-р Иванов.",
        context={},
    )

    med_appt = [r for r in result.reminders if r.title.startswith("Medical appointment")]
    assert med_appt
    assert "Ivanov" in med_appt[0].title or "Иванов" in med_appt[0].title
    dt = datetime.fromisoformat(med_appt[0].due_at)
    assert dt.hour == 14
    assert dt.minute == 30


def test_ai_client_handles_specialist_cardiologist() -> None:
    client = AIClient()
    result = client.analyze_conversation(
        conversation_id="conv-13",
        transcript_text="В петък трябва да отида при кардиолог.",
        context={},
    )

    med_appt = [r for r in result.reminders if r.title.startswith("Medical appointment")]
    assert med_appt
    assert "cardiologist" in med_appt[0].title


def test_ai_client_handles_complex_bulgarian_birthday_instruction_with_address_and_time() -> None:
    client = AIClient()
    text = "Здрасти бабо утре трябва да отидеш на рожден ден на леля Димче на адрес София 21 в 3:00."
    result = client.analyze_conversation(
        conversation_id="conv-10",
        transcript_text=text,
        context={},
    )

    birthday = next((r for r in result.reminders if r.title.startswith("Birthday party")), None)
    assert birthday is not None
    assert birthday.due_at is not None
    assert "София 21" in birthday.details
    dt = datetime.fromisoformat(birthday.due_at)
    assert dt.hour == 15
