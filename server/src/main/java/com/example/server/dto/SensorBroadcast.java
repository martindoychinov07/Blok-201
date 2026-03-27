package com.example.server.dto;

import java.time.Instant;

public class SensorBroadcast {

    private String deviceId;
    private double temperature;
    private Double humidity;
    private Double pressure;
    private String status;
    private String timestamp;

    public SensorBroadcast() {}

    public SensorBroadcast(SensorData data) {
        this.deviceId    = data.getDeviceId() != null ? data.getDeviceId() : "ESP_UNKNOWN";
        this.temperature = data.getTemperature();
        this.humidity    = data.getHumidity();
        this.pressure    = data.getPressure();
        this.status      = data.getStatus();
        this.timestamp   = Instant.now().toString();
    }

    public String getDeviceId()    { return deviceId; }
    public double getTemperature() { return temperature; }
    public Double getHumidity()    { return humidity; }
    public Double getPressure()    { return pressure; }
    public String getStatus()      { return status; }
    public String getTimestamp()   { return timestamp; }
}