package com.example.server.mqtt;

import com.example.server.dto.SensorData;
import com.example.server.service.DeviceSessionService;
import com.example.server.service.MqttAckPublisher;
import com.example.server.service.SensorService;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class MqttListener {

    @Autowired
    private SensorService sensorService;

    @Autowired
    private DeviceSessionService deviceSessionService;

    @Autowired
    private MqttAckPublisher mqttAckPublisher;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @PostConstruct
    public void init() {
        System.out.println("MQTT LISTENER LOADED");
    }

    @ServiceActivator(inputChannel = "mqttInputChannel")
    public void handleMessage(String payload) {
        try {
            JsonNode root = objectMapper.readTree(payload);

            if (isHandshake(root)) {
                handleHandshake(root);
                return;
            }

            SensorData data = objectMapper.treeToValue(root, SensorData.class);
            if (data.getDeviceId() == null || data.getDeviceId().isBlank()) {
                data.setDeviceId(root.path("device_id").asText(root.path("deviceId").asText("ESP_UNKNOWN")));
            }

            DeviceSessionService.SessionInfo session = deviceSessionService.findByDevice(data.getDeviceId());
            if (session != null) {
                data.setAckNumber(session.ackNumber);
                data.setPatientId(session.patientId);
            }

            sensorService.processSensorData(data);

        } catch (Exception e) {
            System.err.println("Failed to parse MQTT message: " + payload);
            e.printStackTrace();
        }
    }

    private boolean isHandshake(JsonNode root) {
        String type = root.path("type").asText("").trim().toLowerCase();
        if ("hello".equals(type) || "handshake".equals(type)) {
            return true;
        }
        return root.has("username") && root.has("role") && root.has("deviceId");
    }

    private void handleHandshake(JsonNode root) throws Exception {
        String username = root.path("username").asText(root.path("patient_id").asText("patient-unknown"));
        String role = root.path("role").asText("user");
        String patientId = root.path("patient_id").asText(username);
        String deviceId = root.path("deviceId").asText(root.path("device_id").asText("ESP_UNKNOWN"));

        String replyTopic = root.path("replyTopic").asText("");
        if (replyTopic.isBlank()) {
            replyTopic = "device/" + deviceId + "/ack";
        }

        DeviceSessionService.SessionInfo session = deviceSessionService.openSession(
                username,
                role,
                patientId,
                deviceId,
                replyTopic
        );

        String ftpSession = root.path("ftp_session").asText(root.path("ftpSession").asText(""));
        if (!ftpSession.isBlank()) {
            deviceSessionService.bindFtpSession(session.ackNumber, ftpSession);
        }

        Map<String, Object> ack = new LinkedHashMap<>();
        ack.put("type", "ack");
        ack.put("username", username);
        ack.put("role", role);
        ack.put("patient_id", patientId);
        ack.put("device_id", deviceId);
        ack.put("ack_number", session.ackNumber);
        ack.put("ftp_session", session.ftpSessionId == null ? ("ftp-" + session.ackNumber) : session.ftpSessionId);
        ack.put("reply_topic", replyTopic);

        mqttAckPublisher.publish(replyTopic, objectMapper.writeValueAsString(ack));
        System.out.println("Session opened for device " + deviceId + " ack=" + session.ackNumber + " topic=" + replyTopic);
    }
}
