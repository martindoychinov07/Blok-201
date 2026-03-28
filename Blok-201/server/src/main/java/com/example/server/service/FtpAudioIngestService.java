package com.example.server.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.*;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class FtpAudioIngestService {

    private static final Pattern ACK_PATTERN = Pattern.compile("ack[_-]?(\\d+)", Pattern.CASE_INSENSITIVE);

    @Autowired
    private DeviceSessionService deviceSessionService;

    @Autowired
    private AiCoreClientService aiCoreClientService;

    @Autowired
    private AiEventStore aiEventStore;

    @Value("${ftp.inbox-dir:}")
    private String ftpInboxDir;

    @Scheduled(fixedDelayString = "${ftp.scan-ms:1000}")
    public void scanFtpInbox() {
        if (ftpInboxDir == null || ftpInboxDir.isBlank()) {
            return;
        }

        Path dir = Paths.get(ftpInboxDir);
        if (!Files.isDirectory(dir)) {
            return;
        }

        try (DirectoryStream<Path> stream = Files.newDirectoryStream(dir, "*.wav")) {
            for (Path file : stream) {
                processFile(file);
            }
        } catch (Exception ignored) {
            // keep loop resilient
        }
    }

    private void processFile(Path file) {
        String name = file.getFileName().toString();
        Long ack = extractAck(name);
        if (ack == null) {
            return;
        }

        DeviceSessionService.SessionInfo session = deviceSessionService.findByAck(ack);
        if (session == null || session.patientId == null || session.patientId.isBlank()) {
            return;
        }

        try {
            byte[] audio = Files.readAllBytes(file);
            Map<String, Object> aiResult = aiCoreClientService.transcribeAndAnalyze(session.patientId, audio, Instant.now());

            @SuppressWarnings("unchecked")
            Map<String, Object> analysis = aiResult.get("analysis") instanceof Map<?, ?>
                    ? (Map<String, Object>) aiResult.get("analysis") : Map.of();

            if (analysis.isEmpty()) {
                return;
            }

            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("transcript_id", analysis.get("transcript_id"));
            payload.put("patient_id", session.patientId);
            payload.put("timestamp", Instant.now().toString());
            payload.put("text", aiResult.getOrDefault("text", ""));
            payload.put("source", analysis.getOrDefault("source", "unknown"));
            payload.put("warning", analysis.get("warning"));
            payload.put("saved", analysis.getOrDefault("saved", Map.of()));
            payload.put("analysis", analysis.getOrDefault("analysis", analysis));

            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("origin", "ftp-audio");
            meta.put("ack_number", ack);
            meta.put("file_name", name);
            payload.put("meta", meta);

            aiEventStore.addEvent(payload, "ftp-audio");
            Files.deleteIfExists(file);
        } catch (IOException ignored) {
            // keep file for next retry
        } catch (Exception ignored) {
            // keep file for next retry
        }
    }

    private Long extractAck(String fileName) {
        Matcher m = ACK_PATTERN.matcher(fileName);
        if (m.find()) {
            try {
                return Long.parseLong(m.group(1));
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return null;
    }
}
