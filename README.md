# Dementia Edge MVP (ESP32 + AI Backend)

Production-like MVP where ESP32 sends sensor/speech events and backend performs AI extraction.

## What is implemented

- FastAPI backend with REST + WebSocket alerts
- SQLite schema for patients, sensors, transcripts, facts, reminders, alerts
- Event-driven pipeline for:
  - transcript ingestion from ESP32 or simulator
  - GPS geofence detection
  - accelerometer fall detection
  - AI extraction into structured memory
- Alert fan-out to dashboard and optional Telegram

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

If you use ESP32 input, set `DEMO_MODE=false` in `.env`.

## Main endpoints

- `GET /health`
- `POST /ingest/transcript`
- `POST /ingest/gps`
- `POST /ingest/accelerometer`
- `GET /alerts`
- `POST /alerts/{alert_id}/ack`
- `GET /patients/{patient_id}/profile`
- `GET /patients/{patient_id}/memory`
- `GET /patients/{patient_id}/context`
- `GET /patients/{patient_id}/reminders`
- `GET /patients/{patient_id}/events`
- `POST /patients/{patient_id}/remember`
- `PATCH /patients/{patient_id}/reminders/{reminder_id}`
- `WS /ws/alerts`

## Notes

- API key for ingest is `X-Device-Key` header and must match `INGEST_SHARED_KEY`.
- Open `http://localhost:8000/` for dashboard.

## ESP32 MVP flow

1. ESP32 sends text transcript chunks to `/ingest/transcript`.
2. Backend runs extraction and writes memory/facts/reminders.
3. ESP32 sends GPS and accelerometer samples.
4. Backend triggers geofence/fall alerts and pushes to dashboard.
5. Caregivers inspect alerts and memory via web UI.

See `firmware/esp32_mvp/esp32_mvp.ino` for firmware skeleton.

## Live microphone testing from PC

1. Open dashboard at `http://localhost:8000/`
2. Set patient/device/key fields in "Live Mic Ingest"
3. Click `Start Listening`
4. Speak in short sentences
5. Transcribed chunks are sent continuously; after pause (default 5s) dashboard sends flush marker
6. Memory, reminders, and alerts update live

Notes:
- Browser STT uses Web Speech API (`SpeechRecognition` or `webkitSpeechRecognition`).
- Chrome/Edge work best.
- `POST /ingest/transcript` supports flush-only calls (`{"flush": true}`) to finalize current conversation buffer.

## Reminder behavior

- Reminders now stack when details/schedule differ.
- Exact reminder duplicates are merged.
- Reminder states can be changed (`active`, `done`, `cancelled`, `stale`).
- Doctor medication instructions like "take pills every day" create recurring reminders.
- High-priority reminders and important memory notes also generate live alerts.
- Social events (e.g. birthday party invitations) are extracted to reminders and the Events panel.
- Includes baseline bilingual keyword support for English and Bulgarian phrases.

## Gemini Transcript Analysis API (new)

This repository now also includes a focused backend flow for transcript-to-structured-memory using Gemini:

- `POST /transcripts/analyze`
- Raw transcript is saved first
- Transcript is analyzed with Gemini
- Structured JSON is validated with Pydantic
- People, appointments, reminders, and facts are persisted in SQLite

### Run Gemini backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
# set GEMINI_API_KEY in .env
# optional: set TRANSCRIPT_DATABASE_PATH=./data/transcript_analysis.db
# optional: GEMINI_FALLBACK_ENABLED=true (default) to keep pipeline working when Gemini quota is exhausted
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Sample request:

```bash
curl -X POST "http://localhost:8001/transcripts/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "p_001",
    "timestamp": "2026-03-26T14:30:00Z",
    "text": "Tomorrow at 3 PM we have an appointment with Dr. Ivanov. Maria will take him."
  }'
```

If Gemini is unavailable (quota/rate-limit/key issues) and `GEMINI_FALLBACK_ENABLED=true`,
the endpoint still returns `200` with `"source": "fallback"` and a warning message.

Quick raw-text request (no JSON body):

```bash
curl -X POST "http://localhost:8001/transcripts/analyze-plain?patient_id=p_001" \
  -H "Content-Type: text/plain" \
  --data-binary "Tomorrow at 3 PM appointment with Dr. Ivanov, then call Maria and buy aspirin."
```

### Upload WAV for transcription

Endpoint:
- `POST /transcripts/transcribe?patient_id=p_001&analyze=true`

Send raw WAV bytes with `Content-Type: audio/wav`.

Example:

```bash
curl -X POST "http://localhost:8001/transcripts/transcribe?patient_id=p_001&analyze=true" \
  -H "Content-Type: audio/wav" \
  --data-binary @sample.wav
```

Notes:
- Requires local transcription engine: `pip install faster-whisper`
- UI supports this at `http://localhost:8001/ui` in the **Upload WAV** card.

### Basic microphone UI

- Open `http://localhost:8001/ui`
- Click `Start Listening`
- Speak normally; final transcript chunks are buffered
- After pause timeout (default 5s), buffered text is sent to `/transcripts/analyze`
- `Send Buffer Now` forces immediate analysis
- UI includes reminder visualization, appointment feed, facts feed, and analysis timeline

Additional memory endpoints used by the UI:
- `GET /patients/{patient_id}/reminders?status=active|done|cancelled|stale|all`
- `PATCH /patients/{patient_id}/reminders/{reminder_id}`
- `GET /patients/{patient_id}/appointments`
- `GET /patients/{patient_id}/facts`

### Generic server integration (webhook)

The AI backend can forward every analyzed transcript to any external server via a configurable webhook.

Enable in `.env`:

```bash
ANALYSIS_WEBHOOK_ENABLED=true
ANALYSIS_WEBHOOK_URL=https://your-server.example.com/api/ai/transcript-analysis
ANALYSIS_WEBHOOK_TIMEOUT_SEC=5
ANALYSIS_WEBHOOK_BEARER_TOKEN=
```

When enabled, every successful `POST /transcripts/analyze`, `POST /transcripts/analyze-plain`, and `/transcripts/transcribe?analyze=true` sends a best-effort POST to `ANALYSIS_WEBHOOK_URL`.

Webhook failures do not break persistence in the AI backend; they are returned in the API `warning` field.

Data flow:
- `curl` text to `app.main` (`8001`) via `/transcripts/analyze` or `/transcripts/analyze-plain`
- AI extraction + persistence happens in SQLite
- same normalized payload is sent to your external server webhook

### Blok-201 integration (recommended setup now)

Use the same webhook integration and point it to the Blok-201 ingestion endpoint.

In `.env`:

```bash
ANALYSIS_WEBHOOK_ENABLED=true
ANALYSIS_WEBHOOK_URL=http://localhost:5000/api/ai/transcript-analysis
ANALYSIS_WEBHOOK_TIMEOUT_SEC=5
ANALYSIS_WEBHOOK_BEARER_TOKEN=
```

Run both services:

```bash
# AI core
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Blok-201 server
cd Blok-201
npm install
npm start
```

Open UIs:
- AI core UI: `http://localhost:8001/ui`
- Blok-201 live monitor: `http://localhost:5000/`

Quick check:
1. Send text from embedded gateway route:
   - `POST http://localhost:5000/api/embedded/text`
2. Send WAV from embedded gateway route:
   - `POST http://localhost:5000/api/embedded/audio` (multipart)
3. Open `http://localhost:5000/` and confirm event/alerts/reminders update.

Example embedded text curl:

```bash
curl -X POST "http://localhost:5000/api/embedded/text" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "p_001",
    "text": "Tomorrow at 3 PM appointment with Dr. Ivanov, then call Maria and buy aspirin."
  }'
```

Example embedded WAV curl (server auto-transcribes + analyzes):

```bash
curl -X POST "http://localhost:5000/api/embedded/audio" \
  -F "patient_id=p_001" \
  -F "audio=@sample.wav"
```
