# Blok-201

This is the original Spring server branch (login + dashboard + calendar) with AI integration added on top.

## Run

```bash
cd server
sh mvnw spring-boot:run
```

Default UI URL: `http://localhost:8081/`

## Keep existing frontend, add AI only

The existing auth/dashboard/calendar frontend remains intact.
New AI panel is added inside the dashboard, without replacing the original UI flow.

## AI core connection

Configure in `server/src/main/resources/application.properties` via env vars:

```bash
AI_CORE_BASE_URL=http://localhost:8001
AI_CORE_TIMEOUT_MS=25000
AI_DEFAULT_PATIENT_ID=p_001
EMBEDDED_INGEST_TOKEN=
AI_WEBHOOK_TOKEN=
```

## New server endpoints

- `POST /api/embedded/text` -> forwards transcript JSON to AI `/transcripts/analyze`
- `POST /api/embedded/audio` -> forwards WAV to AI `/transcripts/transcribe?analyze=true`
- `POST /api/embedded/audio/raw` -> same as above but raw WAV body
- `POST /api/ai/transcript-analysis` -> optional webhook ingest from AI side
- `GET /api/ai/transcript-analysis`
- `GET /api/ai/transcript-analysis/latest`
- `GET /api/ai/alerts` / `PATCH /api/ai/alerts/{id}`
- `GET /api/ai/reminders` / `PATCH /api/ai/reminders/{id}`
- `GET /api/ai/config`

## MQTT + FTP session mapping

Embedded flow now supports session handshake over MQTT:

1. Device publishes hello to `device/hello` with:
   - `username` (unique patient username)
   - `role` (`user`)
   - `patient_id`
   - `deviceId`
   - `replyTopic`
2. Server replies on `replyTopic` with `ack_number`.
3. Device includes this `ack_number` in sensor payloads and FTP audio naming.

Server properties:

```bash
MQTT_BROKER_URI=tcp://localhost:1883
MQTT_INBOUND_CLIENT_ID=spring-server-client
MQTT_OUTBOUND_CLIENT_ID=spring-server-publisher
```

### FTP audio bridge

If your SIM900A uploads WAV files through FTP, name files like:

`ack_<ack_number>_<anything>.wav`

Then point `FTP_INBOX_DIR` to the folder where uploaded files appear on the server host.
Server polls this folder and maps each file to a session by `ack_number`, forwards to AI transcribe/analyze, and deletes the file on success.

```bash
FTP_INBOX_DIR=/var/dementiaaid/ftp-inbox
FTP_SCAN_MS=1000
```

This keeps local storage usage low.

## Firmware

Embedded sketch is in `firmware/esp32_mvp/esp32_mvp.ino` and now targets:

- SIM900A internet (TinyGSM)
- MQTT sensor publish every 50ms (GPS + MPU)
- MQTT handshake/ack session
- 5-second WAV segment loop
- FTP upload with `ack_number` in filename
- immediate local file delete after successful upload

## Embedded example

```bash
curl -X POST "http://localhost:8081/api/embedded/text" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "p_001",
    "text": "Tomorrow at 3 PM appointment with Dr. Ivanov, then call Maria and buy aspirin."
  }'
```
