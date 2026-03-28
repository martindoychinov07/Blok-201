from pathlib import Path

import pytest

from app.services.gemini_service import GeminiInvalidResponseError, GeminiService


def test_gemini_parser_accepts_json_code_fence() -> None:
    prompt_path = Path(__file__).resolve().parents[1] / "app" / "prompts" / "extraction_prompt.txt"
    service = GeminiService(
        api_key="fake-key",
        model="gemini-1.5-flash",
        timeout_sec=10,
        prompt_path=str(prompt_path),
    )

    raw = """
```json
{
  "people": [{"name": "Maria", "relationship": "daughter"}],
  "appointments": [{"title": "Doctor visit", "doctor": "Dr. Ivanov", "time_text": "tomorrow 3 PM"}],
  "reminders": [{"type": "task", "text": "Take pills", "time_text": "daily morning"}],
  "medications": ["Aspirin"],
  "safety_notes": ["possible confusion"],
  "important_facts": ["Maria will take him"]
}
```
"""

    parsed = service._parse_analysis_json(raw)
    assert parsed.people[0].name == "Maria"
    assert parsed.reminders[0].time_text == "daily morning"


def test_gemini_parser_rejects_invalid_json() -> None:
    prompt_path = Path(__file__).resolve().parents[1] / "app" / "prompts" / "extraction_prompt.txt"
    service = GeminiService(
        api_key="fake-key",
        model="gemini-1.5-flash",
        timeout_sec=10,
        prompt_path=str(prompt_path),
    )

    with pytest.raises(GeminiInvalidResponseError):
        service._parse_analysis_json("not a json payload")
