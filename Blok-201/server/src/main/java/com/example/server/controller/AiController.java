package com.example.server.controller;

import com.example.server.dto.AiDto;
import com.example.server.model.User;
import com.example.server.repository.UserRepository;
import com.example.server.service.AiCoreClientService;
import com.example.server.service.AiEventStore;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class AiController {

    @Autowired
    private AiCoreClientService aiCoreClientService;

    @Autowired
    private AiEventStore aiEventStore;

    @Autowired
    private UserRepository userRepository;

    @Value("${ai.default-patient-id:p_001}")
    private String defaultPatientId;

    @Value("${ai.embedded-token:}")
    private String embeddedToken;

    @Value("${ai.webhook-token:}")
    private String webhookToken;

    @Value("${ai.core.base-url:http://localhost:8001}")
    private String aiBaseUrl;

    @GetMapping("/ai/config")
    public Map<String, Object> config() {
        return Map.of(
                "status", "ok",
                "ai_base_url", aiBaseUrl,
                "embedded_auth_required", !blank(embeddedToken),
                "webhook_auth_required", !blank(webhookToken)
        );
    }

    @PostMapping("/embedded/text")
    public ResponseEntity<?> embeddedText(
            @RequestBody AiDto.EmbeddedTextRequest request,
            Authentication authentication,
            HttpServletRequest httpRequest
    ) {
        if (!allowToken(httpRequest, embeddedToken, "x-embedded-token")) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Unauthorized request"));
        }

        String text = safe(request.text);
        if (blank(text)) {
            return ResponseEntity.badRequest().body(Map.of("error", "text is required"));
        }

        String patientId = resolvePatientId(request.patientId, authentication);
        Instant timestamp = parseTimestamp(request.timestamp);

        try {
            Map<String, Object> aiResponse = aiCoreClientService.analyzeText(patientId, text, timestamp);
            Map<String, Object> payload = normalizePayload(
                    patientId,
                    timestamp,
                    text,
                    aiResponse,
                    "embedded-text",
                    request.sensor
            );

            AiEventStore.AiEvent event = aiEventStore.addEvent(payload, "embedded-text");
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of(
                    "status", "accepted",
                    "eventId", event.eventId,
                    "receivedAt", event.receivedAt,
                    "ai", aiResponse
            ));
        } catch (Exception ex) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
                    "error", "AI analyze request failed",
                    "details", compact(ex.getMessage())
            ));
        }
    }

    @PostMapping(value = "/embedded/audio", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> embeddedAudio(
            @RequestParam(value = "patient_id", required = false) String patientIdParam,
            @RequestParam(value = "timestamp", required = false) String timestamp,
            @RequestPart("audio") MultipartFile audio,
            Authentication authentication,
            HttpServletRequest httpRequest
    ) {
        if (!allowToken(httpRequest, embeddedToken, "x-embedded-token")) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Unauthorized request"));
        }

        if (audio == null || audio.isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "audio file is required"));
        }

        String patientId = resolvePatientId(patientIdParam, authentication);
        Instant ts = parseTimestamp(timestamp);

        try {
            Map<String, Object> aiResult = aiCoreClientService.transcribeAndAnalyze(patientId, audio.getBytes(), ts);
            Map<String, Object> aiAnalyze = mapOf(aiResult.get("analysis"));
            if (aiAnalyze.isEmpty()) {
                return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of("error", "AI did not return analysis payload"));
            }

            Map<String, Object> payload = normalizePayload(
                    patientId,
                    ts,
                    safe(aiResult.get("text")),
                    aiAnalyze,
                    "embedded-audio",
                    null
            );
            Map<String, Object> meta = mapOf(payload.get("meta"));
            meta.put("duration_seconds", aiResult.get("duration_seconds"));
            meta.put("file_name", audio.getOriginalFilename());
            payload.put("meta", meta);

            AiEventStore.AiEvent event = aiEventStore.addEvent(payload, "embedded-audio");
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of(
                    "status", "accepted",
                    "eventId", event.eventId,
                    "receivedAt", event.receivedAt,
                    "transcript", safe(aiResult.get("text")),
                    "duration_seconds", aiResult.get("duration_seconds"),
                    "ai", aiAnalyze
            ));
        } catch (Exception ex) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
                    "error", "AI transcribe request failed",
                    "details", compact(ex.getMessage())
            ));
        }
    }

    @PostMapping(value = "/embedded/audio/raw", consumes = {
            "audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream"
    })
    public ResponseEntity<?> embeddedAudioRaw(
            @RequestParam(value = "patient_id", required = false) String patientIdParam,
            @RequestParam(value = "timestamp", required = false) String timestamp,
            @RequestBody byte[] body,
            Authentication authentication,
            HttpServletRequest httpRequest
    ) {
        if (!allowToken(httpRequest, embeddedToken, "x-embedded-token")) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Unauthorized request"));
        }

        if (body == null || body.length == 0) {
            return ResponseEntity.badRequest().body(Map.of("error", "raw wav body is required"));
        }

        String patientId = resolvePatientId(patientIdParam, authentication);
        Instant ts = parseTimestamp(timestamp);

        try {
            Map<String, Object> aiResult = aiCoreClientService.transcribeAndAnalyze(patientId, body, ts);
            Map<String, Object> aiAnalyze = mapOf(aiResult.get("analysis"));
            if (aiAnalyze.isEmpty()) {
                return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of("error", "AI did not return analysis payload"));
            }

            Map<String, Object> payload = normalizePayload(
                    patientId,
                    ts,
                    safe(aiResult.get("text")),
                    aiAnalyze,
                    "embedded-audio-raw",
                    null
            );

            Map<String, Object> meta = mapOf(payload.get("meta"));
            meta.put("duration_seconds", aiResult.get("duration_seconds"));
            payload.put("meta", meta);

            AiEventStore.AiEvent event = aiEventStore.addEvent(payload, "embedded-audio-raw");
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of(
                    "status", "accepted",
                    "eventId", event.eventId,
                    "receivedAt", event.receivedAt,
                    "transcript", safe(aiResult.get("text")),
                    "duration_seconds", aiResult.get("duration_seconds"),
                    "ai", aiAnalyze
            ));
        } catch (Exception ex) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
                    "error", "AI transcribe request failed",
                    "details", compact(ex.getMessage())
            ));
        }
    }

    @PostMapping("/ai/transcript-analysis")
    public ResponseEntity<?> receiveAiWebhook(@RequestBody Map<String, Object> payload, HttpServletRequest request) {
        if (!allowToken(request, webhookToken, "x-webhook-token")) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Unauthorized request"));
        }

        if (payload == null || payload.isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "JSON payload required"));
        }

        AiEventStore.AiEvent event = aiEventStore.addEvent(payload, "core-webhook");
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of(
                "status", "accepted",
                "eventId", event.eventId,
                "receivedAt", event.receivedAt
        ));
    }

    @GetMapping("/ai/transcript-analysis")
    public Map<String, Object> listEvents(@RequestParam(defaultValue = "50") int limit) {
        List<AiEventStore.AiEvent> items = aiEventStore.listEvents(limit);
        return Map.of(
                "status", "ok",
                "count", items.size(),
                "items", items
        );
    }

    @GetMapping("/ai/transcript-analysis/latest")
    public Map<String, Object> latestEvent() {
        AiEventStore.AiEvent event = aiEventStore.latestEvent();
        if (event == null) {
            return Map.of("status", "empty");
        }
        return Map.of(
                "status", "ok",
                "eventId", event.eventId,
                "receivedAt", event.receivedAt,
                "payload", event.payload
        );
    }

    @GetMapping("/ai/alerts")
    public Map<String, Object> listAlerts(
            @RequestParam(defaultValue = "active") String status,
            @RequestParam(value = "patient_id", required = false) String patientId,
            @RequestParam(defaultValue = "100") int limit,
            Authentication authentication
    ) {
        String resolvedPatient = resolvePatientId(patientId, authentication);
        List<AiEventStore.AiAlert> items = aiEventStore.listAlerts(status, resolvedPatient, limit);
        return Map.of(
                "status", "ok",
                "count", items.size(),
                "items", items
        );
    }

    @PatchMapping("/ai/alerts/{alertId}")
    public ResponseEntity<?> patchAlert(@PathVariable String alertId, @RequestBody AiDto.StatusUpdateRequest request) {
        String status = safe(request.status).toLowerCase();
        if (!status.equals("active") && !status.equals("acknowledged") && !status.equals("dismissed")) {
            return ResponseEntity.badRequest().body(Map.of("error", "status must be active|acknowledged|dismissed"));
        }
        AiEventStore.AiAlert alert = aiEventStore.updateAlertStatus(alertId, status);
        if (alert == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "alert not found"));
        }
        return ResponseEntity.ok(Map.of("status", "ok", "item", alert));
    }

    @GetMapping("/ai/reminders")
    public Map<String, Object> listReminders(
            @RequestParam(defaultValue = "active") String status,
            @RequestParam(value = "patient_id", required = false) String patientId,
            @RequestParam(defaultValue = "200") int limit,
            Authentication authentication
    ) {
        String resolvedPatient = resolvePatientId(patientId, authentication);
        List<AiEventStore.AiReminder> items = aiEventStore.listReminders(status, resolvedPatient, limit);
        return Map.of(
                "status", "ok",
                "count", items.size(),
                "items", items
        );
    }

    @PatchMapping("/ai/reminders/{reminderId}")
    public ResponseEntity<?> patchReminder(@PathVariable String reminderId, @RequestBody AiDto.StatusUpdateRequest request) {
        String status = safe(request.status).toLowerCase();
        if (!status.equals("active") && !status.equals("done") && !status.equals("cancelled") && !status.equals("stale")) {
            return ResponseEntity.badRequest().body(Map.of("error", "status must be active|done|cancelled|stale"));
        }
        AiEventStore.AiReminder reminder = aiEventStore.updateReminderStatus(reminderId, status);
        if (reminder == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "reminder not found"));
        }
        return ResponseEntity.ok(Map.of("status", "ok", "item", reminder));
    }

    private Map<String, Object> normalizePayload(
            String patientId,
            Instant timestamp,
            String text,
            Map<String, Object> aiResponse,
            String origin,
            Map<String, Object> sensor
    ) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("transcript_id", aiResponse.get("transcript_id"));
        payload.put("patient_id", patientId);
        payload.put("timestamp", timestamp.toString());
        payload.put("text", text);
        payload.put("source", aiResponse.getOrDefault("source", "unknown"));
        payload.put("warning", aiResponse.get("warning"));
        payload.put("saved", mapOf(aiResponse.get("saved")));
        payload.put("analysis", mapOf(aiResponse.get("analysis")));

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("origin", origin);
        meta.put("sensor", sensor);
        payload.put("meta", meta);
        return payload;
    }

    private String resolvePatientId(String explicit, Authentication authentication) {
        if (!blank(explicit)) {
            return explicit.trim();
        }

        if (authentication != null && authentication.isAuthenticated() && !"anonymousUser".equals(authentication.getName())) {
            User user = userRepository.findByUsername(authentication.getName()).orElse(null);
            if (user != null) {
                if (user.getRole() == User.Role.CAREGIVER && user.getPatient() != null && user.getPatient().getId() != null) {
                    return user.getPatient().getId().toString();
                }
                if (user.getId() != null) {
                    return user.getId().toString();
                }
            }
        }

        return defaultPatientId;
    }

    private Instant parseTimestamp(String raw) {
        if (blank(raw)) {
            return Instant.now();
        }
        try {
            return Instant.parse(raw.trim());
        } catch (DateTimeParseException ex) {
            return Instant.now();
        }
    }

    private boolean allowToken(HttpServletRequest request, String expected, String headerName) {
        if (blank(expected)) {
            return true;
        }

        String auth = safe(request.getHeader("Authorization"));
        String custom = safe(request.getHeader(headerName));
        return auth.equals("Bearer " + expected) || custom.equals(expected);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> mapOf(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> out = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                out.put(String.valueOf(entry.getKey()), entry.getValue());
            }
            return out;
        }
        return new LinkedHashMap<>();
    }

    private String safe(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private boolean blank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private String compact(String raw) {
        if (raw == null) {
            return "";
        }
        String v = raw.replaceAll("\\s+", " ").trim();
        if (v.length() > 240) {
            return v.substring(0, 237) + "...";
        }
        return v;
    }
}
