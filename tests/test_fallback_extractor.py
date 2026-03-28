from app.services.fallback_extractor import FallbackExtractor


def test_fallback_extractor_preserves_day_and_time_text() -> None:
    extractor = FallbackExtractor()
    result = extractor.analyze("Tomorrow at 3 PM we have an appointment with Dr. Ivanov.")

    assert result.appointments
    assert result.appointments[0].time_text is not None
    assert "tomorrow" in result.appointments[0].time_text.lower()
    assert "3" in result.appointments[0].time_text


def test_fallback_extractor_no_medication_false_positive_for_take_him() -> None:
    extractor = FallbackExtractor()
    result = extractor.analyze("Tomorrow at 3 PM appointment with Dr. Ivanov. Maria will take him.")

    med_reminders = [r for r in result.reminders if r.type == "medication"]
    assert not med_reminders
