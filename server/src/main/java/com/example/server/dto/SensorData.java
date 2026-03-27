package com.example.server.dto;

public class SensorData {

    private String deviceId;
    private double temperature;
    private Double humidity;
    private Double pressure;
    private String status;

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public double getTemperature() { return temperature; }
    public void setTemperature(double temperature) { this.temperature = temperature; }

    public Double getHumidity() { return humidity; }
    public void setHumidity(Double humidity) { this.humidity = humidity; }

    public Double getPressure() { return pressure; }
    public void setPressure(Double pressure) { this.pressure = pressure; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}