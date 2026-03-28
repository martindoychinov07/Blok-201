import pytest

from app.schemas import AnalysisResult, TranscriptIn


def test_transcript_schema_rejects_empty_text() -> None:
    with pytest.raises(ValueError):
        TranscriptIn(
            patient_id="p_001",
            timestamp="2026-03-26T14:30:00Z",
            text="   ",
        )


def test_analysis_result_schema_defaults() -> None:
    result = AnalysisResult.model_validate({})
    assert result.people == []
    assert result.appointments == []
    assert result.reminders == []
    assert result.medications == []
