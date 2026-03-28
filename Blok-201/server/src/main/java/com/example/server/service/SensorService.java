package com.example.server.service;

import com.example.server.dto.SensorBroadcast;
import com.example.server.dto.SensorData;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.util.concurrent.atomic.AtomicReference;

@Service
public class SensorService {

    private SimpMessagingTemplate messagingTemplate;
    private final AtomicReference<SensorBroadcast> latestBroadcast = new AtomicReference<>();

    @Autowired
    public SensorService(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    public void processSensorData(SensorData data) {
        System.out.println("Processing sensor data — lat: " + data.getLatitude()
                + " lon: " + data.getLongitude()
                + (data.getDeviceId() != null ? " | device: " + data.getDeviceId() : ""));

        SensorBroadcast broadcast = new SensorBroadcast(data);
        latestBroadcast.set(broadcast);

        messagingTemplate.convertAndSend("/topic/sensor", broadcast);
    }

    public SensorBroadcast latest() {
        return latestBroadcast.get();
    }
}
