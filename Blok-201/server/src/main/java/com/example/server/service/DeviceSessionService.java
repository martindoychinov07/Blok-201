package com.example.server.service;

import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class DeviceSessionService {

    private final AtomicLong nextAck = new AtomicLong(100000);
    private final Map<Long, SessionInfo> byAck = new ConcurrentHashMap<>();
    private final Map<String, SessionInfo> byDevice = new ConcurrentHashMap<>();

    public SessionInfo openSession(String username, String role, String patientId, String deviceId, String replyTopic) {
        long ack = nextAck.incrementAndGet();
        SessionInfo info = new SessionInfo();
        info.ackNumber = ack;
        info.username = username;
        info.role = role;
        info.patientId = patientId;
        info.deviceId = deviceId;
        info.replyTopic = replyTopic;
        info.createdAt = Instant.now();
        info.lastSeenAt = Instant.now();

        byAck.put(ack, info);
        if (deviceId != null && !deviceId.isBlank()) {
            byDevice.put(deviceId, info);
        }
        return info;
    }

    public SessionInfo findByAck(long ack) {
        SessionInfo info = byAck.get(ack);
        if (info != null) {
            info.lastSeenAt = Instant.now();
        }
        return info;
    }

    public SessionInfo findByDevice(String deviceId) {
        if (deviceId == null || deviceId.isBlank()) {
            return null;
        }
        SessionInfo info = byDevice.get(deviceId);
        if (info != null) {
            info.lastSeenAt = Instant.now();
        }
        return info;
    }

    public void bindFtpSession(long ack, String ftpSessionId) {
        SessionInfo info = byAck.get(ack);
        if (info != null) {
            info.ftpSessionId = ftpSessionId;
            info.lastSeenAt = Instant.now();
        }
    }

    public static class SessionInfo {
        public long ackNumber;
        public String username;
        public String role;
        public String patientId;
        public String deviceId;
        public String replyTopic;
        public String ftpSessionId;
        public Instant createdAt;
        public Instant lastSeenAt;
    }
}
