package com.example.server.service;

import com.example.server.dto.SensorBroadcast;
import com.example.server.dto.SensorData;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class SensorService {

    private final SimpMessagingTemplate messagingTemplate;

    public void processSensorData(SensorData data) {
        System.out.println("Processing sensor data — temp: " + data.getTemperature()
                + (data.getDeviceId() != null ? " | device: " + data.getDeviceId() : ""));

        SensorBroadcast broadcast = new SensorBroadcast(data);

        messagingTemplate.convertAndSend("/topic/sensor", broadcast);
    }
}