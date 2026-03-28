#include "dementia_device.h"

#include <FS.h>
#include <SD.h>
#include <Wire.h>
#include <cmath>
#include <cstring>
#include <esp_system.h>

#include "app_config.h"
#include "audio_wav.h"

namespace {
#if defined(HSPI)
constexpr uint8_t kSdSpiHost = HSPI;
#elif defined(FSPI)
constexpr uint8_t kSdSpiHost = FSPI;
#else
constexpr uint8_t kSdSpiHost = 0;
#endif
}

DementiaDevice* DementiaDevice::instance_ = nullptr;

DementiaDevice::DementiaDevice()
    : modemSerial_(1),
      gpsSerial_(2),
      sdSpi_(kSdSpiHost),
      modem_(modemSerial_),
      mqttTransport_(modem_),
      mqttClient_(mqttTransport_),
      ftpCtrlTransport_(modem_),
      ftpDataTransport_(modem_),
      ftpUploader_(ftpCtrlTransport_, ftpDataTransport_) {}

void DementiaDevice::begin() {
  instance_ = this;

  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("=== Dementia Assist Device (ESP32-S3) ===");

  if (!roleIsValid()) {
    Serial.println("[CONFIG] PATIENT_ROLE must be 'user' or 'caregiver'");
    while (true) {
      delay(1000);
    }
  }

  if (!validateSecuritySettings()) {
    while (true) {
      delay(1000);
    }
  }

  deviceId_ = generateDeviceId(10);
  Serial.printf("[DEVICE] Username=%s Role=%s DeviceId=%s\n",
                cfg::PATIENT_USERNAME,
                cfg::PATIENT_ROLE,
                deviceId_.c_str());

  if (cfg::PIN_GPS_EN >= 0) {
    pinMode(cfg::PIN_GPS_EN, OUTPUT);
    digitalWrite(cfg::PIN_GPS_EN, HIGH);
    gpsEnabled_ = true;
  }

  gpsSerial_.begin(cfg::GPS_BAUD, SERIAL_8N1, cfg::PIN_GPS_RX, cfg::PIN_GPS_TX);

  if (!initMpu() || !initStorage() || !initModemAndData()) {
    Serial.println("[BOOT] Initialization failed");
    while (true) {
      delay(1000);
    }
  }

  if (!audiowav::initBluetoothMicI2S(
          cfg::AUDIO_SAMPLE_RATE, cfg::PIN_BT_I2S_BCLK, cfg::PIN_BT_I2S_WS, cfg::PIN_BT_I2S_DIN)) {
    Serial.println("[BOOT] Bluetooth headset mic input init failed");
    while (true) {
      delay(1000);
    }
  }

  mqttClient_.setServer(cfg::MQTT_HOST, cfg::MQTT_PORT);
  mqttClient_.setBufferSize(1024);
  mqttClient_.setKeepAlive(30);
  mqttClient_.setCallback(mqttCallbackTrampoline);

  telemetryQueue_ = xQueueCreate(cfg::TELEMETRY_QUEUE_DEPTH, sizeof(TelemetrySample));
  audioQueue_ = xQueueCreate(cfg::AUDIO_QUEUE_DEPTH, sizeof(AudioJob));

  if (telemetryQueue_ == nullptr || audioQueue_ == nullptr) {
    Serial.println("[BOOT] Queue allocation failed");
    while (true) {
      delay(1000);
    }
  }

  lastMovementMs_ = millis();

  xTaskCreatePinnedToCore(sensorTaskTrampoline, "sensorTask", 8192, this, 2, nullptr, 0);
  xTaskCreatePinnedToCore(commsTaskTrampoline, "commsTask", 16384, this, 3, nullptr, 0);
  xTaskCreatePinnedToCore(audioTaskTrampoline, "audioTask", 12288, this, 1, nullptr, 1);

  Serial.println("[BOOT] Tasks started");
}

void DementiaDevice::loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));
}

void DementiaDevice::sensorTaskTrampoline(void* arg) {
  static_cast<DementiaDevice*>(arg)->sensorTask();
}

void DementiaDevice::audioTaskTrampoline(void* arg) {
  static_cast<DementiaDevice*>(arg)->audioTask();
}

void DementiaDevice::commsTaskTrampoline(void* arg) {
  static_cast<DementiaDevice*>(arg)->commsTask();
}

void DementiaDevice::mqttCallbackTrampoline(char* topic, uint8_t* payload, unsigned int length) {
  if (instance_ != nullptr) {
    instance_->onMqttMessage(topic, payload, length);
  }
}

void DementiaDevice::sensorTask() {
  sensors_event_t accel;
  sensors_event_t gyro;
  sensors_event_t temp;
  uint32_t lastDebugPrintMs = 0;

  for (;;) {
    while (gpsSerial_.available()) {
      gps_.encode(gpsSerial_.read());
    }

    mpu_.getEvent(&accel, &gyro, &temp);
    const uint32_t now = millis();

    const float magnitude = sqrtf(accel.acceleration.x * accel.acceleration.x +
                                  accel.acceleration.y * accel.acceleration.y +
                                  accel.acceleration.z * accel.acceleration.z);
    const float delta = fabsf(magnitude - lastAccMagnitude_);
    lastAccMagnitude_ = magnitude;

    if (delta > cfg::MOTION_DELTA_THRESHOLD) {
      lastMovementMs_ = now;
    }

    const bool moving = (now - lastMovementMs_) <= cfg::STATIONARY_TIMEOUT_MS;
    if (moving && !gpsEnabled_) {
      setGpsEnabled(true);
      Serial.println("[GPS] Enabled (movement detected)");
    } else if (!moving && gpsEnabled_) {
      setGpsEnabled(false);
      Serial.println("[GPS] Disabled (stationary)");
    }

    const bool gpsLocationValid = gps_.location.isValid();
    const bool gpsSpeedValid = gps_.speed.isValid();
    const bool gpsAltitudeValid = gps_.altitude.isValid();
    const bool gpsSatsValid = gps_.satellites.isValid();
    const bool gpsHdopValid = gps_.hdop.isValid();

    const float lat = gpsLocationValid ? static_cast<float>(gps_.location.lat()) : NAN;
    const float lng = gpsLocationValid ? static_cast<float>(gps_.location.lng()) : NAN;
    const float speedKmph = gpsSpeedValid ? static_cast<float>(gps_.speed.kmph()) : NAN;
    const float altitude = gpsAltitudeValid ? static_cast<float>(gps_.altitude.meters()) : NAN;
    const uint8_t sats = gpsSatsValid ? static_cast<uint8_t>(gps_.satellites.value()) : 0;
    const float hdop = gpsHdopValid ? static_cast<float>(gps_.hdop.hdop()) : NAN;

    if (cfg::SERIAL_SENSOR_DEBUG && (now - lastDebugPrintMs >= cfg::SERIAL_SENSOR_DEBUG_PERIOD_MS)) {
      Serial.printf(
          "[SENS] t=%lu moving=%u gpsEn=%u ack=%u | IMU a(%.2f %.2f %.2f) g(%.2f %.2f %.2f) T=%.2f | GPS fix=%u lat=%.6f lng=%.6f spd=%.2f alt=%.2f sats=%u hdop=%.2f\n",
          static_cast<unsigned long>(now),
          moving ? 1 : 0,
          gpsEnabled_ ? 1 : 0,
          ackReceived_ ? 1 : 0,
          accel.acceleration.x,
          accel.acceleration.y,
          accel.acceleration.z,
          gyro.gyro.x,
          gyro.gyro.y,
          gyro.gyro.z,
          temp.temperature,
          gpsLocationValid ? 1 : 0,
          lat,
          lng,
          speedKmph,
          altitude,
          sats,
          hdop);
      lastDebugPrintMs = now;
    }

    if (ackReceived_ && (moving || moving != lastMovingState_)) {
      TelemetrySample sample{};
      sample.uptimeMs = now;
      sample.moving = moving;
      sample.ax = accel.acceleration.x;
      sample.ay = accel.acceleration.y;
      sample.az = accel.acceleration.z;
      sample.gx = gyro.gyro.x;
      sample.gy = gyro.gyro.y;
      sample.gz = gyro.gyro.z;
      sample.tempC = temp.temperature;

      sample.lat = lat;
      sample.lng = lng;
      sample.speedKmph = speedKmph;
      sample.altitude = altitude;
      sample.sats = sats;

      enqueueTelemetry(sample);
    }

    lastMovingState_ = moving;
    vTaskDelay(pdMS_TO_TICKS(cfg::SENSOR_PERIOD_MS));
  }
}

void DementiaDevice::audioTask() {
  for (;;) {
    if (!sessionReady_) {
      vTaskDelay(pdMS_TO_TICKS(200));
      continue;
    }

    if (!ensureSessionDir()) {
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }

    AudioJob job{};
    snprintf(job.path,
             sizeof(job.path),
             "/audio/%lu/%010lu.wav",
             static_cast<unsigned long>(ackNumber_),
             static_cast<unsigned long>(millis()));

    if (audiowav::recordBluetoothMicSegment(job.path, cfg::AUDIO_SAMPLE_RATE, cfg::AUDIO_SEGMENT_SECONDS)) {
      job.retries = 0;
      enqueueAudio(job);
      Serial.printf("[AUDIO] Segment ready: %s\n", job.path);
    } else {
      Serial.println("[AUDIO] Segment recording failed");
    }
  }
}

void DementiaDevice::commsTask() {
  uint32_t lastInitTryMs = 0;

  for (;;) {
    if (!modem_.isNetworkConnected()) {
      Serial.println("[MODEM] Network lost, reconnecting...");
      modem_.waitForNetwork(30000L);
      modem_.gprsConnect(cfg::APN, cfg::GPRS_USER, cfg::GPRS_PASS);
    }

    if (!mqttClient_.connected()) {
      if (!connectMqtt()) {
        vTaskDelay(pdMS_TO_TICKS(2000));
        continue;
      }
      initPublished_ = false;
    }

    mqttClient_.loop();

    if (!ackReceived_) {
      const uint32_t now = millis();
      if (!initPublished_ || (now - lastInitTryMs) >= cfg::INIT_RETRY_MS) {
        initPublished_ = publishInitMessage();
        lastInitTryMs = now;
      }
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }

    if (!ftpReady_) {
      if (ftpUploader_.begin(cfg::FTP_HOST, cfg::FTP_PORT, cfg::FTP_USER, cfg::FTP_PASS, ackNumber_)) {
        ftpReady_ = true;
        sessionReady_ = true;
        Serial.println("[FTP] Session ready");
      } else {
        Serial.println("[FTP] Session init failed, retrying...");
        vTaskDelay(pdMS_TO_TICKS(3000));
        continue;
      }
    }

    TelemetrySample telemetry;
    if (xQueueReceive(telemetryQueue_, &telemetry, 0) == pdTRUE) {
      if (!publishTelemetry(telemetry)) {
        Serial.println("[MQTT] Telemetry publish failed");
      }
    }

    AudioJob job;
    if (xQueueReceive(audioQueue_, &job, 0) == pdTRUE) {
      const char* fileName = strrchr(job.path, '/');
      fileName = (fileName != nullptr) ? (fileName + 1) : job.path;

      const bool ok = ftpUploader_.uploadFile(job.path, fileName);
      if (ok) {
        SD.remove(job.path);
        Serial.printf("[FTP] Uploaded and removed: %s\n", job.path);
      } else {
        job.retries++;
        if (job.retries <= cfg::AUDIO_MAX_RETRIES) {
          enqueueAudio(job);
          Serial.printf("[FTP] Upload failed, requeued (%u): %s\n", job.retries, job.path);
        } else {
          SD.remove(job.path);
          Serial.printf("[FTP] Upload dropped after retries: %s\n", job.path);
        }
      }
    }

    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void DementiaDevice::onMqttMessage(char* topic, uint8_t* payload, unsigned int length) {
  if (strcmp(topic, cfg::MQTT_ACK_TOPIC) != 0) {
    return;
  }

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.printf("[MQTT] ACK parse error: %s\n", err.c_str());
    return;
  }

  if (doc["deviceId"].is<const char*>()) {
    const char* forDevice = doc["deviceId"].as<const char*>();
    if (strcmp(forDevice, deviceId_.c_str()) != 0) {
      return;
    }
  }

  uint32_t ack = 0;
  if (doc["ack"].is<uint32_t>()) {
    ack = doc["ack"].as<uint32_t>();
  } else if (doc["acknowledgmentNumber"].is<uint32_t>()) {
    ack = doc["acknowledgmentNumber"].as<uint32_t>();
  }

  if (ack == 0) {
    Serial.println("[MQTT] ACK payload missing valid acknowledgment number");
    return;
  }

  ackNumber_ = ack;
  ackReceived_ = true;
  Serial.printf("[MQTT] ACK received: %lu\n", static_cast<unsigned long>(ackNumber_));
}

bool DementiaDevice::roleIsValid() const {
  return strcmp(cfg::PATIENT_ROLE, "user") == 0 || strcmp(cfg::PATIENT_ROLE, "caregiver") == 0;
}

bool DementiaDevice::validateSecuritySettings() const {
  const bool mqttSecure = cfg::MQTT_USE_TLS && cfg::MODEM_SUPPORTS_TLS;
  const bool ftpSecure = cfg::FTP_USE_TLS && cfg::MODEM_SUPPORTS_TLS;

  Serial.printf("[SECURITY] MQTT secure requested: %s\n", cfg::MQTT_USE_TLS ? "yes" : "no");
  Serial.printf("[SECURITY] FTP secure requested : %s\n", cfg::FTP_USE_TLS ? "yes" : "no");
  Serial.printf("[SECURITY] Modem TLS support    : %s\n", cfg::MODEM_SUPPORTS_TLS ? "yes" : "no");
  Serial.printf("[SECURITY] MQTT secure active   : %s\n", mqttSecure ? "yes" : "no");
  Serial.printf("[SECURITY] FTP secure active    : %s\n", ftpSecure ? "yes" : "no");

  if (cfg::REQUIRE_SECURE_LINKS && (!mqttSecure || !ftpSecure)) {
    Serial.println("[SECURITY] REQUIRED secure links are not available.");
    return false;
  }

  return true;
}

bool DementiaDevice::initStorage() {
  Serial.printf("[SD] SPI host=%u SCK=%d MISO=%d MOSI=%d CS=%d\n",
                static_cast<unsigned>(kSdSpiHost),
                cfg::PIN_SD_SCK,
                cfg::PIN_SD_MISO,
                cfg::PIN_SD_MOSI,
                cfg::PIN_SD_CS);

  pinMode(cfg::PIN_SD_MISO, INPUT_PULLUP);
  pinMode(cfg::PIN_SD_MOSI, OUTPUT);
  pinMode(cfg::PIN_SD_SCK, OUTPUT);
  pinMode(cfg::PIN_SD_CS, OUTPUT);

  digitalWrite(cfg::PIN_SD_MOSI, HIGH);
  digitalWrite(cfg::PIN_SD_SCK, HIGH);
  digitalWrite(cfg::PIN_SD_CS, HIGH);
  delay(20);

  sdSpi_.begin(cfg::PIN_SD_SCK, cfg::PIN_SD_MISO, cfg::PIN_SD_MOSI, cfg::PIN_SD_CS);

  const uint32_t speeds[] = {
      400000U,
      1000000U,
      cfg::SD_SPI_HZ,
      10000000U,
  };

  bool mounted = false;
  for (size_t i = 0; i < (sizeof(speeds) / sizeof(speeds[0])); ++i) {
    const uint32_t hz = speeds[i];
    Serial.printf("[SD] Trying mount at %lu Hz...\n", static_cast<unsigned long>(hz));
    if (SD.begin(cfg::PIN_SD_CS, sdSpi_, hz)) {
      mounted = true;
      Serial.printf("[SD] Mounted at %lu Hz\n", static_cast<unsigned long>(hz));
      break;
    }

    SD.end();
    delay(120);
  }

  if (!mounted) {
    Serial.println("[SD] Initialization failed on all SPI speeds");
    return false;
  }

  const uint8_t cardType = SD.cardType();
  if (cardType == CARD_NONE) {
    Serial.println("[SD] Card not detected");
    return false;
  }

  Serial.printf("[SD] Card size: %llu MB\n", SD.cardSize() / (1024ULL * 1024ULL));

  if (!SD.exists("/audio") && !SD.mkdir("/audio")) {
    Serial.println("[SD] Failed to create /audio directory");
    return false;
  }

  Serial.println("[SD] OK");
  return true;
}

bool DementiaDevice::initMpu() {
  Wire.begin(cfg::PIN_I2C_SDA, cfg::PIN_I2C_SCL);
  if (!mpu_.begin(0x68, &Wire)) {
    Serial.println("[MPU6050] Not found");
    return false;
  }

  mpu_.setAccelerometerRange(MPU6050_RANGE_4_G);
  mpu_.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu_.setFilterBandwidth(MPU6050_BAND_21_HZ);

  Serial.println("[MPU6050] OK");
  return true;
}

void DementiaDevice::pulseModemPwrKey() {
  if (cfg::PIN_MODEM_PWRKEY < 0) {
    return;
  }
  pinMode(cfg::PIN_MODEM_PWRKEY, OUTPUT);
  digitalWrite(cfg::PIN_MODEM_PWRKEY, LOW);
  delay(200);
  digitalWrite(cfg::PIN_MODEM_PWRKEY, HIGH);
  delay(1200);
  digitalWrite(cfg::PIN_MODEM_PWRKEY, LOW);
  delay(3000);
}

bool DementiaDevice::initModemAndData() {
  modemSerial_.begin(cfg::MODEM_BAUD, SERIAL_8N1, cfg::PIN_MODEM_RX, cfg::PIN_MODEM_TX);
  pulseModemPwrKey();

  if (!modem_.testAT(10000)) {
    Serial.println("[MODEM] No response on AT");
    return false;
  }

  modem_.restart();
  Serial.printf("[MODEM] %s\n", modem_.getModemInfo().c_str());

  Serial.println("[MODEM] Waiting for network...");
  if (!modem_.waitForNetwork(90000L)) {
    Serial.println("[MODEM] Network not available");
    return false;
  }

  Serial.println("[MODEM] Connecting GPRS...");
  if (!modem_.gprsConnect(cfg::APN, cfg::GPRS_USER, cfg::GPRS_PASS)) {
    Serial.println("[MODEM] GPRS failed");
    return false;
  }

  Serial.printf("[MODEM] GPRS connected, IP: %s\n", modem_.localIP().toString().c_str());
  return true;
}

bool DementiaDevice::connectMqtt() {
  if (mqttClient_.connected()) {
    return true;
  }

  const String clientId = "esp32s3-" + deviceId_;
  bool ok = false;

  if (strlen(cfg::MQTT_USER) > 0) {
    ok = mqttClient_.connect(clientId.c_str(), cfg::MQTT_USER, cfg::MQTT_PASS);
  } else {
    ok = mqttClient_.connect(clientId.c_str());
  }

  if (!ok) {
    Serial.printf("[MQTT] Connect failed, state=%d\n", mqttClient_.state());
    return false;
  }

  if (!mqttClient_.subscribe(cfg::MQTT_ACK_TOPIC)) {
    Serial.println("[MQTT] Subscribe ACK failed");
    mqttClient_.disconnect();
    return false;
  }

  Serial.println("[MQTT] Connected");
  return true;
}

bool DementiaDevice::publishInitMessage() {
  JsonDocument doc;
  doc["username"] = cfg::PATIENT_USERNAME;
  doc["deviceId"] = deviceId_;
  doc["role"] = cfg::PATIENT_ROLE;
  doc["ackTopic"] = cfg::MQTT_ACK_TOPIC;

  String payload;
  serializeJson(doc, payload);

  const bool ok = mqttClient_.publish(cfg::MQTT_INIT_TOPIC, payload.c_str(), true);
  Serial.printf("[MQTT] Init publish: %s\n", ok ? "OK" : "FAIL");
  return ok;
}

bool DementiaDevice::publishTelemetry(const TelemetrySample& sample) {
  JsonDocument doc;
  doc["ack"] = ackNumber_;
  doc["deviceId"] = deviceId_;
  doc["tsMs"] = sample.uptimeMs;
  doc["moving"] = sample.moving;

  JsonObject imu = doc["imu"].to<JsonObject>();
  imu["ax"] = sample.ax;
  imu["ay"] = sample.ay;
  imu["az"] = sample.az;
  imu["gx"] = sample.gx;
  imu["gy"] = sample.gy;
  imu["gz"] = sample.gz;
  imu["temp"] = sample.tempC;

  JsonObject gpsObj = doc["gps"].to<JsonObject>();
  gpsObj["lat"] = sample.lat;
  gpsObj["lng"] = sample.lng;
  gpsObj["speedKmph"] = sample.speedKmph;
  gpsObj["altitude"] = sample.altitude;
  gpsObj["sats"] = sample.sats;
  gpsObj["enabled"] = gpsEnabled_;

  String payload;
  serializeJson(doc, payload);
  return mqttClient_.publish(cfg::MQTT_TELEMETRY_TOPIC, payload.c_str(), false);
}

bool DementiaDevice::ensureSessionDir() {
  if (!ackReceived_) {
    return false;
  }

  char dirPath[48];
  snprintf(dirPath, sizeof(dirPath), "/audio/%lu", static_cast<unsigned long>(ackNumber_));
  if (!SD.exists(dirPath) && !SD.mkdir(dirPath)) {
    Serial.printf("[SD] Failed to create session dir: %s\n", dirPath);
    return false;
  }

  return true;
}

String DementiaDevice::generateDeviceId(size_t len) const {
  static const char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  String out;
  out.reserve(len);
  for (size_t i = 0; i < len; ++i) {
    const uint32_t idx = esp_random() % (sizeof(alphabet) - 1);
    out += alphabet[idx];
  }
  return out;
}

void DementiaDevice::enqueueTelemetry(const TelemetrySample& sample) {
  if (xQueueSend(telemetryQueue_, &sample, 0) == pdTRUE) {
    return;
  }

  TelemetrySample drop;
  if (xQueueReceive(telemetryQueue_, &drop, 0) == pdTRUE) {
    xQueueSend(telemetryQueue_, &sample, 0);
  }
}

void DementiaDevice::enqueueAudio(const AudioJob& job) {
  if (xQueueSend(audioQueue_, &job, 0) == pdTRUE) {
    return;
  }

  AudioJob dropped;
  if (xQueueReceive(audioQueue_, &dropped, 0) == pdTRUE) {
    SD.remove(dropped.path);
    xQueueSend(audioQueue_, &job, 0);
  }
}

void DementiaDevice::setGpsEnabled(bool enabled) {
  if (cfg::PIN_GPS_EN >= 0) {
    digitalWrite(cfg::PIN_GPS_EN, enabled ? HIGH : LOW);
  }
  gpsEnabled_ = enabled;
}
