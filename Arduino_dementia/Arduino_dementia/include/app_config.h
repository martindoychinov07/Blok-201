#pragma once

#include <cstddef>
#include <cstdint>

namespace cfg {

// -----------------------------
// Identity and server settings
// -----------------------------
constexpr char PATIENT_USERNAME[] = "patient_demo";
constexpr char PATIENT_ROLE[] = "user";  // "user" or "caregiver"

constexpr char APN[] = "your_apn";
constexpr char GPRS_USER[] = "";
constexpr char GPRS_PASS[] = "";

constexpr char MQTT_HOST[] = "your.server.com";
constexpr uint16_t MQTT_PORT = 1883;
constexpr char MQTT_USER[] = "";
constexpr char MQTT_PASS[] = "";
constexpr char MQTT_INIT_TOPIC[] = "dementia/init";
constexpr char MQTT_ACK_TOPIC[] = "dementia/ack";
constexpr char MQTT_TELEMETRY_TOPIC[] = "dementia/telemetry";

constexpr char FTP_HOST[] = "your.server.com";
constexpr uint16_t FTP_PORT = 21;
constexpr char FTP_USER[] = "ftp_user";
constexpr char FTP_PASS[] = "ftp_pass";

// SIM900A usually does not provide robust modern TLS.
// Keep false for SIM900A; set true only with a modem that supports TLS.
constexpr bool MODEM_SUPPORTS_TLS = false;
constexpr bool MQTT_USE_TLS = false;
constexpr bool FTP_USE_TLS = false;
constexpr bool REQUIRE_SECURE_LINKS = false;

// -----------------------------
// Timing and buffering
// -----------------------------
constexpr uint32_t SENSOR_PERIOD_MS = 50;
constexpr bool SERIAL_SENSOR_DEBUG = true;
constexpr uint32_t SERIAL_SENSOR_DEBUG_PERIOD_MS = 1000;
constexpr uint32_t INIT_RETRY_MS = 4000;
constexpr uint32_t STATIONARY_TIMEOUT_MS = 30000;
constexpr float MOTION_DELTA_THRESHOLD = 0.08f;

constexpr uint16_t AUDIO_SAMPLE_RATE = 8000;
constexpr uint8_t AUDIO_SEGMENT_SECONDS = 5;
constexpr uint8_t AUDIO_MAX_RETRIES = 3;

constexpr size_t TELEMETRY_QUEUE_DEPTH = 120;
constexpr size_t AUDIO_QUEUE_DEPTH = 24;

// -----------------------------
// UART, I2C, SPI pin mapping
// -----------------------------
// SIM900A
constexpr int PIN_MODEM_TX = 15;      // ESP32 TX -> SIM900A RX (through level shift/divider)
constexpr int PIN_MODEM_RX = 16;      // ESP32 RX <- SIM900A TX
constexpr int PIN_MODEM_PWRKEY = 21;  // optional, via transistor
constexpr uint32_t MODEM_BAUD = 9600;

// NEO-6M GPS
constexpr int PIN_GPS_TX = 17;    // ESP32 TX -> GPS RX
constexpr int PIN_GPS_RX = 18;    // ESP32 RX <- GPS TX
constexpr int PIN_GPS_EN = 38;    // set to -1 if your board does not expose GPS EN power control
constexpr uint32_t GPS_BAUD = 9600;

// MPU6050 I2C
constexpr int PIN_I2C_SDA = 8;
constexpr int PIN_I2C_SCL = 9;

// SD card SPI
constexpr int PIN_SD_SCK = 40;
constexpr int PIN_SD_MOSI = 42;
constexpr int PIN_SD_MISO = 41;
constexpr int PIN_SD_CS = 39;
constexpr uint32_t SD_SPI_HZ = 4000000;

// Bluetooth headset microphone input (via external BT audio bridge with I2S PCM output)
// Note: ESP32-S3 cannot capture headset mic directly over Classic Bluetooth HFP.
// Use a bridge module that handles Bluetooth and outputs I2S/PCM to ESP32-S3.
constexpr int PIN_BT_I2S_BCLK = 4;
constexpr int PIN_BT_I2S_WS = 5;
constexpr int PIN_BT_I2S_DIN = 6;

}  // namespace cfg
