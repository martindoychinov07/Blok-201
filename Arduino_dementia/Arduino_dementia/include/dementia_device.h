#pragma once

#include <Arduino.h>

#define TINY_GSM_MODEM_SIM800
#define TINY_GSM_RX_BUFFER 1024

#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <SPI.h>
#include <TinyGPS++.h>
#include <TinyGsmClient.h>

#include "ftp_uploader.h"

class DementiaDevice {
 public:
  DementiaDevice();
  void begin();
  void loop();

 private:
  struct TelemetrySample {
    uint32_t uptimeMs;
    bool moving;
    float ax;
    float ay;
    float az;
    float gx;
    float gy;
    float gz;
    float tempC;
    float lat;
    float lng;
    float speedKmph;
    float altitude;
    uint8_t sats;
  };

  struct AudioJob {
    char path[96];
    uint8_t retries;
  };

  static DementiaDevice* instance_;
  static void sensorTaskTrampoline(void* arg);
  static void audioTaskTrampoline(void* arg);
  static void commsTaskTrampoline(void* arg);
  static void mqttCallbackTrampoline(char* topic, uint8_t* payload, unsigned int length);

  void sensorTask();
  void audioTask();
  void commsTask();
  void onMqttMessage(char* topic, uint8_t* payload, unsigned int length);

  bool roleIsValid() const;
  bool validateSecuritySettings() const;
  bool initStorage();
  bool initMpu();
  bool initModemAndData();
  bool connectMqtt();
  bool publishInitMessage();
  bool publishTelemetry(const TelemetrySample& sample);
  bool ensureSessionDir();
  String generateDeviceId(size_t len) const;
  void pulseModemPwrKey();
  void enqueueTelemetry(const TelemetrySample& sample);
  void enqueueAudio(const AudioJob& job);
  void setGpsEnabled(bool enabled);

  HardwareSerial modemSerial_;
  HardwareSerial gpsSerial_;
  SPIClass sdSpi_;
  TinyGsm modem_;
  TinyGsmClient mqttTransport_;
  PubSubClient mqttClient_;
  TinyGsmClient ftpCtrlTransport_;
  TinyGsmClient ftpDataTransport_;
  FtpUploader ftpUploader_;

  Adafruit_MPU6050 mpu_;
  TinyGPSPlus gps_;

  QueueHandle_t telemetryQueue_ = nullptr;
  QueueHandle_t audioQueue_ = nullptr;

  String deviceId_;
  volatile bool ackReceived_ = false;
  volatile uint32_t ackNumber_ = 0;
  volatile bool ftpReady_ = false;
  volatile bool sessionReady_ = false;
  bool initPublished_ = false;

  bool gpsEnabled_ = true;
  bool lastMovingState_ = true;
  float lastAccMagnitude_ = 9.81f;
  uint32_t lastMovementMs_ = 0;
};
