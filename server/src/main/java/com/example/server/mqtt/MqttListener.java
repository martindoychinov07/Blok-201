package com.example.server.mqtt;

import com.example.server.dto.SensorData;
import com.example.server.service.SensorService;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.stereotype.Service;

@Service
public class MqttListener {

    @Autowired
    private SensorService sensorService;

    private final tools.jackson.databind.ObjectMapper objectMapper = new tools.jackson.databind.ObjectMapper();

    @PostConstruct
    public void init() {
        System.out.println("MQTT LISTENER LOADED");
    }

    @ServiceActivator(inputChannel = "mqttInputChannel")
    public void handleMessage(String payload) {
        try {
            SensorData data = objectMapper.readValue(payload, SensorData.class);

            System.out.println("Received temperature: " + data.getTemperature());

            sensorService.processSensorData(data);

        } catch (Exception e) {
            System.err.println("Failed to parse MQTT message: " + payload);
            e.printStackTrace();
        }
    }
}