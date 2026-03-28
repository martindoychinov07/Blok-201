package com.example.server.dto;

public class SensorData {

    private String patientId;
    private String deviceId;
    private Long ackNumber;
    private Double latitude;
    private Double longitude;
    private Double lat;
    private Double lon;
    private Double lng;
    private Double speed;
    private Double speedKmh;
    private Double speedKph;
    private Double ax;
    private Double ay;
    private Double az;
    private String status;

    public String getPatientId() { return patientId; }
    public void setPatientId(String patientId) { this.patientId = patientId; }

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public Long getAckNumber() { return ackNumber; }
    public void setAckNumber(Long ackNumber) { this.ackNumber = ackNumber; }

    public Double getLatitude() { return latitude; }
    public void setLatitude(Double latitude) { this.latitude = latitude; }

    public Double getLongitude() { return longitude; }
    public void setLongitude(Double longitude) { this.longitude = longitude; }

    public Double getLat() { return lat; }
    public void setLat(Double lat) { this.lat = lat; }

    public Double getLon() { return lon; }
    public void setLon(Double lon) { this.lon = lon; }

    public Double getLng() { return lng; }
    public void setLng(Double lng) { this.lng = lng; }

    public Double getSpeed() { return speed; }
    public void setSpeed(Double speed) { this.speed = speed; }

    public Double getSpeedKmh() { return speedKmh; }
    public void setSpeedKmh(Double speedKmh) { this.speedKmh = speedKmh; }

    public Double getSpeedKph() { return speedKph; }
    public void setSpeedKph(Double speedKph) { this.speedKph = speedKph; }

    public Double getAx() { return ax; }
    public void setAx(Double ax) { this.ax = ax; }

    public Double getAy() { return ay; }
    public void setAy(Double ay) { this.ay = ay; }

    public Double getAz() { return az; }
    public void setAz(Double az) { this.az = az; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
