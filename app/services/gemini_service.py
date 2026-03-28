import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas import AnalysisResult


class GeminiServiceError(Exception):
    pass


class GeminiMissingApiKeyError(GeminiServiceError):
    pass


class GeminiInvalidResponseError(GeminiServiceError):
    pass


@dataclass
class GeminiService:
    api_key: str
    model: str
    timeout_sec: int
    prompt_path: str

    def __post_init__(self) -> None:
        self._client = None
        self._prompt = Path(self.prompt_path).read_text(encoding="utf-8")

    def _lazy_client(self):
        if self._client is not None:
            return self._client
        try:
            from google import genai
        except Exception as exc:  # pragma: no cover
            raise GeminiServiceError("google-genai SDK is not installed") from exc
        self._client = genai.Client(api_key=self.api_key)
        return self._client

    def analyze_transcript(self, transcript_text: str) -> AnalysisResult:
        if not self.api_key:
            raise GeminiMissingApiKeyError("GEMINI_API_KEY is missing")

        prompt = self._build_prompt(transcript_text)
        response_text = self._call_model(prompt)
        return self._parse_analysis_json(response_text)

    def _build_prompt(self, transcript_text: str) -> str:
        return f"{self._prompt}\n\nTranscript:\n{transcript_text.strip()}"

    def _call_model(self, prompt: str) -> str:
        client = self._lazy_client()
        from google.genai import types

        candidate_models = [
            self.model,
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash",
        ]
        seen = set()
        ordered_models = []
        for item in candidate_models:
            if item and item not in seen:
                ordered_models.append(item)
                seen.add(item)

        last_exc: Exception | None = None
        response = None
        errors_by_model: list[str] = []
        for model_name in ordered_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                        max_output_tokens=1200,
                    ),
                )
                break
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                errors_by_model.append(f"{model_name}: {exc}")
                if (
                    "not found" in msg
                    or "unsupported" in msg
                    or "model" in msg
                    or "resource_exhausted" in msg
                    or "quota" in msg
                    or " 429 " in f" {msg} "
                ):
                    continue
                raise GeminiServiceError(f"Gemini API request failed: {exc}") from exc

        if response is None:
            assert last_exc is not None
            joined = " | ".join(errors_by_model[-3:]) if errors_by_model else str(last_exc)
            raise GeminiServiceError(f"Gemini API request failed: {joined}") from last_exc

        text = getattr(response, "text", None)
        if text and text.strip():
            return text

        try:
            # Fallback parse if response.text is empty.
            candidates = getattr(response, "candidates", [])
            if not candidates:
                raise GeminiInvalidResponseError("Gemini response has no candidates")
            parts = candidates[0].content.parts
            collected = []
            for part in parts:
                value = getattr(part, "text", None)
                if value:
                    collected.append(value)
            raw = "\n".join(collected).strip()
            if not raw:
                raise GeminiInvalidResponseError("Gemini response did not contain text")
            return raw
        except GeminiServiceError:
            raise
        except Exception as exc:
            raise GeminiInvalidResponseError("Unable to parse Gemini response text") from exc

    def _parse_analysis_json(self, raw: str) -> AnalysisResult:
        cleaned = self._strip_code_fences(raw)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            payload = self._try_extract_json_object(cleaned)
            if payload is None:
                raise GeminiInvalidResponseError(f"Gemini returned invalid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise GeminiInvalidResponseError("Gemini JSON must be an object")

        try:
            return AnalysisResult.model_validate(payload)
        except Exception as exc:
            raise GeminiInvalidResponseError(f"Gemini JSON schema mismatch: {exc}") from exc

    def _try_extract_json_object(self, text: str) -> dict[str, Any] | None:
        # Fallback for responses like: "Here is JSON: {...}"
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        candidate = match.group(0)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _strip_code_fences(self, raw: str) -> str:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 2:
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
        return text
