package com.example.server.service;

import com.example.server.dto.SensorData;
import org.springframework.stereotype.Service;

@Service
public class SensorService {

    public void processSensorData(SensorData data) {
        // later: save to DB
        System.out.println("Processing: " + data.getTemperature());
    }
}