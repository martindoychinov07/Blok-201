package com.example.server.controller;

import com.example.server.dto.SensorBroadcast;
import com.example.server.service.SensorService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/sensor")
public class SensorController {

    private SensorService sensorService;

    @Autowired
    public SensorController(SensorService sensorService) {
        this.sensorService = sensorService;
    }

    @GetMapping("/latest")
    public Map<String, Object> latest() {
        SensorBroadcast latest = sensorService.latest();
        if (latest == null) {
            return Map.of("status", "empty");
        }
        return Map.of(
                "status", "ok",
                "item", latest
        );
    }
}
