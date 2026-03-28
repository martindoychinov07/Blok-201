import io
import os
import tempfile
import wave
from dataclasses import dataclass


class TranscriptionServiceError(Exception):
    pass


class TranscriptionEngineMissingError(TranscriptionServiceError):
    pass


class InvalidWavAudioError(TranscriptionServiceError):
    pass


@dataclass
class AudioTranscriptionService:
    model_name: str = "tiny"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str | None = None

    def __post_init__(self) -> None:
        self._model = None

    def _lazy_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # pragma: no cover
            raise TranscriptionEngineMissingError(
                "faster-whisper is not installed. Install with: pip install faster-whisper"
            ) from exc

        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        return self._model

    def transcribe_wav_bytes(self, audio_bytes: bytes) -> tuple[str, float]:
        if not audio_bytes:
            raise InvalidWavAudioError("Empty audio payload")

        duration_sec = self._validate_and_get_duration(audio_bytes)

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
                temp.write(audio_bytes)
                temp_path = temp.name

            model = self._lazy_model()
            segments, _info = model.transcribe(
                temp_path,
                language=self.language,
                vad_filter=True,
                beam_size=1,
            )
            text_parts = []
            for seg in segments:
                t = (seg.text or "").strip()
                if t:
                    text_parts.append(t)
            transcript_text = " ".join(text_parts).strip()
            if not transcript_text:
                raise TranscriptionServiceError("Transcription returned empty text")
            return transcript_text, duration_sec
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _validate_and_get_duration(self, audio_bytes: bytes) -> float:
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                if rate <= 0:
                    raise InvalidWavAudioError("Invalid WAV sample rate")
                duration = frames / float(rate)
                return round(duration, 3)
        except InvalidWavAudioError:
            raise
        except Exception as exc:
            raise InvalidWavAudioError("Uploaded file is not a valid WAV audio") from exc
