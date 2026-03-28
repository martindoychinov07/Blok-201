package com.example.server.dto;

import java.time.Instant;

public class SensorBroadcast {

    private String patientId;
    private String deviceId;
    private Long ackNumber;
    private Double latitude;
    private Double longitude;
    private Double speedKmh;
    private Double ax;
    private Double ay;
    private Double az;
    private String status;
    private String timestamp;

    public SensorBroadcast() {}

    public SensorBroadcast(SensorData data) {
        this.patientId   = data.getPatientId();
        this.deviceId    = data.getDeviceId() != null ? data.getDeviceId() : "ESP_UNKNOWN";
        this.ackNumber   = data.getAckNumber();
        this.latitude    = firstNumber(data.getLatitude(), data.getLat());
        this.longitude   = firstNumber(data.getLongitude(), data.getLon(), data.getLng());
        this.speedKmh    = firstNumber(data.getSpeedKmh(), data.getSpeedKph(), data.getSpeed());
        this.ax          = data.getAx();
        this.ay          = data.getAy();
        this.az          = data.getAz();
        this.status      = data.getStatus();
        this.timestamp   = Instant.now().toString();
    }

    private Double firstNumber(Double... values) {
        if (values == null) {
            return null;
        }
        for (Double v : values) {
            if (v != null) {
                return v;
            }
        }
        return null;
    }

    public String getPatientId()   { return patientId; }
    public String getDeviceId()    { return deviceId; }
    public Long getAckNumber()     { return ackNumber; }
    public Double getLatitude()    { return latitude; }
    public Double getLongitude()   { return longitude; }
    public Double getSpeedKmh()    { return speedKmh; }
    public Double getAx()          { return ax; }
    public Double getAy()          { return ay; }
    public Double getAz()          { return az; }
    public String getStatus()      { return status; }
    public String getTimestamp()   { return timestamp; }
}
