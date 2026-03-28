package com.example.server.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

@Service
public class AiEventStore {

    private final List<AiEvent> events = new ArrayList<>();
    private final List<AiAlert> alerts = new ArrayList<>();
    private final List<AiReminder> reminders = new ArrayList<>();

    @Value("${ai.store.max-events:500}")
    private int maxEvents;

    public synchronized AiEvent addEvent(Map<String, Object> payload, String origin) {
        AiEvent event = new AiEvent();
        event.eventId = UUID.randomUUID().toString();
        event.receivedAt = Instant.now();
        event.origin = origin;
        event.payload = payload == null ? new LinkedHashMap<>() : new LinkedHashMap<>(payload);

        events.add(event);
        trim(events, maxEvents);
        deriveAlertsAndReminders(event);
        return event;
    }

    public synchronized List<AiEvent> listEvents(int limit) {
        int safe = Math.max(1, Math.min(limit, Math.max(1, maxEvents)));
        int from = Math.max(0, events.size() - safe);
        return new ArrayList<>(events.subList(from, events.size()));
    }

    public synchronized AiEvent latestEvent() {
        if (events.isEmpty()) {
            return null;
        }
        return events.get(events.size() - 1);
    }

    public synchronized List<AiAlert> listAlerts(String status, String patientId, int limit) {
        String statusNorm = normalize(status);
        String patientNorm = normalize(patientId);
        List<AiAlert> out = new ArrayList<>();
        for (AiAlert item : alerts) {
            if (!"all".equals(statusNorm) && !normalize(item.status).equals(statusNorm)) {
                continue;
            }
            if (!patientNorm.isBlank() && !normalize(item.patientId).equals(patientNorm)) {
                continue;
            }
            out.add(item);
        }
        return tail(out, limit);
    }

    public synchronized AiAlert updateAlertStatus(String alertId, String status) {
        for (AiAlert item : alerts) {
            if (Objects.equals(item.alertId, alertId)) {
                item.status = status;
                item.updatedAt = Instant.now();
                return item;
            }
        }
        return null;
    }

    public synchronized List<AiReminder> listReminders(String status, String patientId, int limit) {
        String statusNorm = normalize(status);
        String patientNorm = normalize(patientId);
        List<AiReminder> out = new ArrayList<>();
        for (AiReminder item : reminders) {
            if (!"all".equals(statusNorm) && !normalize(item.status).equals(statusNorm)) {
                continue;
            }
            if (!patientNorm.isBlank() && !normalize(item.patientId).equals(patientNorm)) {
                continue;
            }
            out.add(item);
        }
        return tail(out, limit);
    }

    public synchronized AiReminder updateReminderStatus(String reminderId, String status) {
        for (AiReminder item : reminders) {
            if (Objects.equals(item.reminderId, reminderId)) {
                item.status = status;
                item.updatedAt = Instant.now();
                return item;
            }
        }
        return null;
    }

    private void deriveAlertsAndReminders(AiEvent event) {
        Map<String, Object> payload = nullSafeMap(event.payload);
        Map<String, Object> analysis = nullSafeMap(payload.get("analysis"));
        String patientId = string(payload.get("patient_id"));

        List<Map<String, Object>> appointments = mapList(analysis.get("appointments"));
        Set<String> seenAppointmentKeys = new HashSet<>();
        Set<String> appointmentSlots = new HashSet<>();

        for (Map<String, Object> appt : appointments) {
            String title = string(appt.get("title"));
            String doctor = string(appt.get("doctor"));
            String time = string(appt.get("time_text"));
            String dedupKey = normalize(patientId) + "|" + normalize(title) + "|" + normalize(doctor) + "|" + normalize(time);
            if (!seenAppointmentKeys.add(dedupKey)) {
                continue;
            }

            String text = title.isBlank() ? "Appointment" : title;
            if (!doctor.isBlank()) {
                text += " with " + doctor;
            }

            appointmentSlots.add(appointmentSlotKey(patientId, time));
            upsertReminder(event.eventId, patientId, "appointment", text, time);
        }

        Set<String> appointmentReminderSeen = new HashSet<>();
        for (Map<String, Object> rem : mapList(analysis.get("reminders"))) {
            String type = string(rem.get("type"));
            String text = string(rem.get("text"));
            String time = string(rem.get("time_text"));

            if (isAppointmentLike(type, text)) {
                String slotKey = appointmentSlotKey(patientId, time);
                if (!appointments.isEmpty()) {
                    if (appointmentSlots.contains(slotKey) || normalize(time).isBlank()) {
                        continue;
                    }
                }

                String fallbackKey = normalize(patientId) + "|" + normalize(text) + "|" + normalize(time);
                if (!appointmentReminderSeen.add(fallbackKey)) {
                    continue;
                }

                upsertReminder(event.eventId, patientId, "appointment", text, time);
                appointmentSlots.add(slotKey);
                continue;
            }

            upsertReminder(event.eventId, patientId, type, text, time);
        }

        for (String med : stringList(analysis.get("medications"))) {
            String medText = "Take " + med;
            boolean already = reminders.stream().anyMatch(r ->
                    normalize(r.patientId).equals(normalize(patientId))
                            && normalize(r.type).equals("medication")
                            && normalize(r.text).equals(normalize(medText))
            );
            if (!already) {
                upsertReminder(event.eventId, patientId, "medication", medText, "");
            }
        }

        String warning = string(payload.get("warning"));
        if (!warning.isBlank()) {
            upsertAlert(event.eventId, patientId, "warning", "AI warning", warning);
        }

        for (String safety : stringList(analysis.get("safety_notes"))) {
            if (!safety.isBlank()) {
                upsertAlert(event.eventId, patientId, "warning", "Safety note detected", safety);
            }
        }

        if (normalize(string(payload.get("source"))).equals("fallback")) {
            upsertAlert(
                    event.eventId,
                    patientId,
                    "info",
                    "Fallback extraction used",
                    "Gemini was unavailable, fallback extractor handled this event."
            );
        }
    }

    private void upsertAlert(String eventId, String patientId, String level, String title, String message) {
        String fp = normalize(patientId) + "|" + normalize(level) + "|" + normalize(title) + "|" + normalize(message);
        for (AiAlert item : alerts) {
            if (normalize(item.fingerprint).equals(fp) && "active".equals(normalize(item.status))) {
                item.lastSeenAt = Instant.now();
                item.eventId = eventId;
                return;
            }
        }

        AiAlert created = new AiAlert();
        created.alertId = UUID.randomUUID().toString();
        created.eventId = eventId;
        created.patientId = patientId;
        created.level = level;
        created.title = title;
        created.message = message;
        created.status = "active";
        created.fingerprint = fp;
        created.createdAt = Instant.now();
        created.lastSeenAt = Instant.now();
        alerts.add(created);
        trim(alerts, maxEvents * 3);
    }

    private void upsertReminder(String eventId, String patientId, String type, String text, String timeText) {
        if (normalize(text).isBlank()) {
            return;
        }
        String safeType = normalize(type).isBlank() ? "task" : type;

        if ("appointment".equals(normalize(safeType))) {
            String normalizedTime = normalizeTimePhrase(timeText);
            if (!normalizedTime.isBlank()) {
                for (AiReminder item : reminders) {
                    if (!normalize(item.patientId).equals(normalize(patientId))) {
                        continue;
                    }
                    if (!"appointment".equals(normalize(item.type))) {
                        continue;
                    }
                    if (normalizeTimePhrase(item.timeText).equals(normalizedTime)) {
                        item.lastSeenAt = Instant.now();
                        item.eventId = eventId;
                        if (!"done".equals(normalize(item.status)) && !"cancelled".equals(normalize(item.status))) {
                            item.status = "active";
                        }
                        return;
                    }
                }
            }
        }

        String key = normalize(patientId) + "|" + normalize(safeType) + "|" + normalize(text) + "|" + normalize(timeText);
        for (AiReminder item : reminders) {
            if (normalize(item.key).equals(key)) {
                item.lastSeenAt = Instant.now();
                item.eventId = eventId;
                if (!"done".equals(normalize(item.status)) && !"cancelled".equals(normalize(item.status))) {
                    item.status = "active";
                }
                return;
            }
        }

        AiReminder created = new AiReminder();
        created.reminderId = UUID.randomUUID().toString();
        created.key = key;
        created.eventId = eventId;
        created.patientId = patientId;
        created.type = safeType;
        created.text = text;
        created.timeText = timeText == null || timeText.isBlank() ? null : timeText;
        created.status = "active";
        created.createdAt = Instant.now();
        created.lastSeenAt = Instant.now();
        reminders.add(created);
        trim(reminders, maxEvents * 6);
    }

    private String normalizeTimePhrase(String raw) {
        String v = normalize(raw);
        if (v.isBlank()) {
            return "";
        }
        v = v.replace(" at ", " ").replace(" в ", " ");
        v = v.replaceAll("\\s+", " ").trim();
        return v;
    }

    private boolean isAppointmentLike(String type, String text) {
        String typeNorm = normalize(type);
        if (typeNorm.equals("appointment") || typeNorm.equals("visit")) {
            return true;
        }
        String textNorm = normalize(text);
        return textNorm.contains("appointment")
                || textNorm.contains("doctor")
                || textNorm.contains("visit")
                || textNorm.contains("преглед")
                || textNorm.contains("доктор")
                || textNorm.contains("лекар");
    }

    private String appointmentSlotKey(String patientId, String timeText) {
        return normalize(patientId) + "|" + normalizeTimePhrase(timeText);
    }

    private String normalize(String raw) {
        if (raw == null) {
            return "";
        }
        return raw.trim().toLowerCase(Locale.ROOT);
    }

    private String string(Object raw) {
        return raw == null ? "" : String.valueOf(raw);
    }

    private Map<String, Object> nullSafeMap(Object value) {
        if (value instanceof Map<?, ?> m) {
            Map<String, Object> out = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : m.entrySet()) {
                out.put(String.valueOf(entry.getKey()), entry.getValue());
            }
            return out;
        }
        return new LinkedHashMap<>();
    }

    private List<Map<String, Object>> mapList(Object value) {
        List<Map<String, Object>> out = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> m) {
                    Map<String, Object> map = new LinkedHashMap<>();
                    for (Map.Entry<?, ?> entry : m.entrySet()) {
                        map.put(String.valueOf(entry.getKey()), entry.getValue());
                    }
                    out.add(map);
                }
            }
        }
        return out;
    }

    private List<String> stringList(Object value) {
        List<String> out = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                if (item != null) {
                    out.add(String.valueOf(item));
                }
            }
        }
        return out;
    }

    private <T> void trim(List<T> list, int max) {
        int safe = Math.max(1, max);
        while (list.size() > safe) {
            list.remove(0);
        }
    }

    private <T> List<T> tail(List<T> in, int limit) {
        int safe = Math.max(1, Math.min(limit, Math.max(1, maxEvents * 6)));
        int from = Math.max(0, in.size() - safe);
        return new ArrayList<>(in.subList(from, in.size()));
    }

    public static class AiEvent {
        public String eventId;
        public Instant receivedAt;
        public String origin;
        public Map<String, Object> payload;
    }

    public static class AiAlert {
        public String alertId;
        public String eventId;
        public String patientId;
        public String level;
        public String title;
        public String message;
        public String status;
        public String fingerprint;
        public Instant createdAt;
        public Instant lastSeenAt;
        public Instant updatedAt;
    }

    public static class AiReminder {
        public String reminderId;
        public String key;
        public String eventId;
        public String patientId;
        public String type;
        public String text;
        public String timeText;
        public String status;
        public Instant createdAt;
        public Instant lastSeenAt;
        public Instant updatedAt;
    }
}
