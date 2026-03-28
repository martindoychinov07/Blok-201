# ESP32 AI MVP Plan

This is the smallest build to validate that AI extraction works with real device input.

## Scope for MVP

- ESP32 sends:
  - transcript text chunks (simulated initially)
  - GPS samples
  - accelerometer samples
- Backend does:
  - AI extraction into structured memory (people, reminders, risks)
  - geofence/fall checks
  - alerts to dashboard

## Why this is enough

- Validates the full AI pipeline on real networked hardware.
- Confirms if extracted memory and risk classification are useful.
- Avoids heavy ESP32-side STT complexity in first iteration.

## Run checklist

1. Configure `.env`:
   - `DEMO_MODE=false`
   - `INGEST_SHARED_KEY=dev-ingest-key`
2. Start backend:
   - `uvicorn src.api.app:app --host 0.0.0.0 --port 8000`
3. Flash firmware:
   - `firmware/esp32_mvp/esp32_mvp.ino`
   - set WiFi and `BACKEND_BASE_URL`
4. Open dashboard:
   - `http://<backend-ip>:8000/`
5. Verify:
   - alerts appear in real time
   - memory facts populate
   - `/patients/patient-001/context` shows people/reminders/risks

## Success criteria

- At least one extracted person profile appears.
- At least one reminder appears from transcript ingestion.
- At least one safety risk appears and triggers warning/critical alert.
- Geofence breach alert appears after GPS drift outside zone.
- Fall alert appears after accelerometer impact + inactivity pattern.

## Next iteration

- Replace transcript simulation with real STT pipeline:
  - option A: ESP32 streams audio to backend for Whisper STT
  - option B: phone companion app does STT and sends text to backend
