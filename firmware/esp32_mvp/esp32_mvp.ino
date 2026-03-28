#define TINY_GSM_MODEM_SIM900

#include <TinyGsmClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <SPIFFS.h>
#include <FS.h>
#include <BluetoothSerial.h>

// -----------------------------------------------------------------------------
// Dementia embedded MVP (SIM900A + MQTT + FTP)
// Requirements implemented:
// - No Wi-Fi usage; internet via SIM900A
// - MQTT handshake -> server returns acknowledgement number
// - GPS + MPU6050 payload publish every 50ms (topic: sensor/data)
// - FTP upload of each recorded 5-second WAV segment with ack in filename
// - File deleted immediately after successful FTP upload
// - Continuous 5-second audio segment loop
//
// Note:
// AirPods microphone over classic Bluetooth HFP is not natively available with
// standard ESP32 Arduino stack. The code keeps Bluetooth active for integration
// and configuration, while recordFiveSecondsToSpiffs() is the pluggable point
// where your actual audio capture pipeline should write PCM/WAV samples.
// -----------------------------------------------------------------------------

// SIM900A serial pins for ESP32 (adjust to your board wiring)
static const int SIM900_TX_PIN = 27;  // ESP32 TX -> SIM900 RX
static const int SIM900_RX_PIN = 26;  // ESP32 RX -> SIM900 TX

HardwareSerial SerialAT(1);
TinyGsm modem(SerialAT);
TinyGsmClient gsmClient(modem);
PubSubClient mqtt(gsmClient);
BluetoothSerial btSerial;

// Cellular APN
const char* APN = "internet";
const char* APN_USER = "";
const char* APN_PASS = "";

// MQTT
const char* MQTT_HOST = "172.20.10.7";
const uint16_t MQTT_PORT = 1883;
const char* MQTT_SENSOR_TOPIC = "sensor/data";
const char* MQTT_HELLO_TOPIC = "device/hello";

// HTTP (for transcript text fallback via Bluetooth input)
const char* SERVER_HTTP_HOST = "172.20.10.7";
const uint16_t SERVER_HTTP_PORT = 8081;

// Identity/session
const char* USERNAME = "patient001";       // unique patient username (letters+digits)
const char* ROLE = "user";
const char* PATIENT_ID = "p_001";
const char* DEVICE_ID = "esp32-001";

// FTP target (SIM900 FTP commands)
const char* FTP_HOST = "172.20.10.7";
const char* FTP_USER = "ftp_user";
const char* FTP_PASS = "ftp_pass";
const char* FTP_PATH = "/incoming/";

// Timing
const unsigned long SENSOR_INTERVAL_MS = 50;      // GPS + MPU publish rate
const unsigned long AUDIO_SEGMENT_MS = 5000;      // 5-second loop

// If upload fails, still delete file to preserve storage.
const bool FORCE_DELETE_ON_UPLOAD_FAILURE = true;

unsigned long lastSensorMs = 0;
unsigned long lastAudioSegmentStartMs = 0;

long ackNumber = -1;
String ackReplyTopic;
String ftpSessionToken = "";

float lat = 42.697700;
float lon = 23.321900;
float speedKmh = 0.0;
float ax = 0.0;
float ay = 0.0;
float az = 1.0;

bool handshakeSent = false;
String btLineBuffer;

String nowIsoLike() {
  unsigned long sec = millis() / 1000;
  unsigned long hh = (sec / 3600) % 24;
  unsigned long mm = (sec / 60) % 60;
  unsigned long ss = sec % 60;
  String out = "1970-01-01T";
  if (hh < 10) out += "0";
  out += String(hh) + ":";
  if (mm < 10) out += "0";
  out += String(mm) + ":";
  if (ss < 10) out += "0";
  out += String(ss) + "Z";
  return out;
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String body;
  for (unsigned int i = 0; i < length; i++) {
    body += (char)payload[i];
  }

  DynamicJsonDocument doc(512);
  if (deserializeJson(doc, body) != DeserializationError::Ok) {
    return;
  }

  String type = doc["type"] | "";
  if (type != "ack") {
    return;
  }

  if (doc["device_id"].is<const char*>()) {
    String dev = doc["device_id"].as<String>();
    if (dev.length() > 0 && dev != DEVICE_ID) {
      return;
    }
  }

  ackNumber = doc["ack_number"] | -1;
  ftpSessionToken = doc["ftp_session"] | "";
}

bool connectCellular() {
  if (!modem.testAT()) {
    modem.restart();
  }

  if (!modem.waitForNetwork(60000L)) {
    return false;
  }

  if (!modem.isNetworkConnected()) {
    return false;
  }

  if (!modem.isGprsConnected()) {
    if (!modem.gprsConnect(APN, APN_USER, APN_PASS)) {
      return false;
    }
  }

  return modem.isGprsConnected();
}

bool connectMqtt() {
  if (mqtt.connected()) {
    return true;
  }

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);

  String clientId = String("sim-") + DEVICE_ID;
  if (!mqtt.connect(clientId.c_str())) {
    return false;
  }

  ackReplyTopic = String("device/") + DEVICE_ID + "/ack";
  mqtt.subscribe(ackReplyTopic.c_str(), 1);
  handshakeSent = false;
  return true;
}

void sendHandshakeIfNeeded() {
  if (!mqtt.connected() || handshakeSent) {
    return;
  }

  DynamicJsonDocument doc(512);
  doc["type"] = "hello";
  doc["username"] = USERNAME;
  doc["role"] = ROLE;
  doc["patient_id"] = PATIENT_ID;
  doc["deviceId"] = DEVICE_ID;
  doc["replyTopic"] = ackReplyTopic;
  doc["timestamp"] = nowIsoLike();

  String payload;
  serializeJson(doc, payload);
  if (mqtt.publish(MQTT_HELLO_TOPIC, payload.c_str(), true)) {
    handshakeSent = true;
  }
}

void readGps() {
  // TODO: replace with real NMEA parser from your GPS module.
  lat += ((float)random(-5, 6)) / 100000.0f;
  lon += ((float)random(-5, 6)) / 100000.0f;
  speedKmh = 1.5f + ((float)random(0, 20)) / 10.0f;
}

void readMpu6050() {
  // TODO: replace with real MPU6050 reads.
  ax = ((float)random(-250, 251)) / 100.0f;
  ay = ((float)random(-250, 251)) / 100.0f;
  az = 1.0f + ((float)random(-40, 41)) / 100.0f;
}

void publishSensorFrame() {
  if (!mqtt.connected()) {
    return;
  }

  readGps();
  readMpu6050();

  DynamicJsonDocument doc(512);
  doc["deviceId"] = DEVICE_ID;
  doc["patient_id"] = PATIENT_ID;
  doc["username"] = USERNAME;
  doc["role"] = ROLE;
  doc["ack_number"] = ackNumber;
  doc["latitude"] = lat;
  doc["longitude"] = lon;
  doc["speedKmh"] = speedKmh;
  doc["ax"] = ax;
  doc["ay"] = ay;
  doc["az"] = az;
  doc["status"] = "ok";
  doc["timestamp"] = nowIsoLike();

  String payload;
  serializeJson(doc, payload);
  mqtt.publish(MQTT_SENSOR_TOPIC, payload.c_str(), false);
}

void writeWavHeader(File& f, uint32_t dataSize, uint32_t sampleRate, uint16_t channels, uint16_t bitsPerSample) {
  uint32_t byteRate = sampleRate * channels * (bitsPerSample / 8);
  uint16_t blockAlign = channels * (bitsPerSample / 8);
  uint32_t riffSize = 36 + dataSize;

  f.write((const uint8_t*)"RIFF", 4);
  f.write((uint8_t*)&riffSize, 4);
  f.write((const uint8_t*)"WAVE", 4);
  f.write((const uint8_t*)"fmt ", 4);

  uint32_t fmtChunkSize = 16;
  uint16_t audioFormat = 1;
  f.write((uint8_t*)&fmtChunkSize, 4);
  f.write((uint8_t*)&audioFormat, 2);
  f.write((uint8_t*)&channels, 2);
  f.write((uint8_t*)&sampleRate, 4);
  f.write((uint8_t*)&byteRate, 4);
  f.write((uint8_t*)&blockAlign, 2);
  f.write((uint8_t*)&bitsPerSample, 2);

  f.write((const uint8_t*)"data", 4);
  f.write((uint8_t*)&dataSize, 4);
}

bool recordFiveSecondsToSpiffs(const char* path) {
  if (!SPIFFS.begin(true)) {
    return false;
  }

  File f = SPIFFS.open(path, FILE_WRITE);
  if (!f) {
    return false;
  }

  // Placeholder silent WAV @16kHz mono 16-bit for 5 seconds.
  // Replace with actual Bluetooth/I2S captured PCM samples.
  const uint32_t sampleRate = 16000;
  const uint16_t channels = 1;
  const uint16_t bits = 16;
  const uint32_t samples = (sampleRate * AUDIO_SEGMENT_MS) / 1000;
  const uint32_t dataSize = samples * channels * (bits / 8);

  writeWavHeader(f, dataSize, sampleRate, channels, bits);

  int16_t sample = 0;
  for (uint32_t i = 0; i < samples; i++) {
    f.write((uint8_t*)&sample, sizeof(sample));
  }

  f.close();
  return true;
}

bool waitForOk(uint32_t timeoutMs) {
  return modem.waitResponse(timeoutMs) == 1;
}

bool httpPostJson(const char* host, uint16_t port, const String& path, const String& body, String* responseOut = nullptr) {
  TinyGsmClient client(modem);
  if (!client.connect(host, port)) {
    return false;
  }

  client.print(String("POST ") + path + " HTTP/1.1\r\n");
  client.print(String("Host: ") + host + ":" + String(port) + "\r\n");
  client.print("Content-Type: application/json\r\n");
  client.print("Connection: close\r\n");
  if (strlen(EMBEDDED_TOKEN) > 0) {
    client.print(String("X-Embedded-Token: ") + EMBEDDED_TOKEN + "\r\n");
  }
  client.print(String("Content-Length: ") + String(body.length()) + "\r\n\r\n");
  client.print(body);

  unsigned long start = millis();
  while (client.connected() && !client.available() && (millis() - start) < 15000UL) {
    delay(10);
  }

  String response;
  while (client.available()) {
    response += (char)client.read();
  }
  client.stop();

  if (responseOut) {
    *responseOut = response;
  }

  int firstSpace = response.indexOf(' ');
  if (firstSpace < 0 || response.length() < firstSpace + 4) {
    return false;
  }
  int status = response.substring(firstSpace + 1, firstSpace + 4).toInt();
  return status >= 200 && status < 300;
}

bool sendTranscriptText(const String& text) {
  DynamicJsonDocument doc(768);
  doc["patient_id"] = PATIENT_ID;
  doc["timestamp"] = nowIsoLike();
  doc["text"] = text;
  JsonObject sensor = doc.createNestedObject("sensor");
  sensor["device"] = DEVICE_ID;
  sensor["ack_number"] = ackNumber;
  sensor["lat"] = lat;
  sensor["lon"] = lon;
  sensor["ax"] = ax;
  sensor["ay"] = ay;
  sensor["az"] = az;

  String payload;
  serializeJson(doc, payload);

  String response;
  return httpPostJson(SERVER_HTTP_HOST, SERVER_HTTP_PORT, "/api/embedded/text", payload, &response);
}

void handleBluetoothTranscriptInput() {
  while (btSerial.available()) {
    char c = (char)btSerial.read();
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      String line = btLineBuffer;
      btLineBuffer = "";
      line.trim();
      if (line.length() > 0) {
        sendTranscriptText(line);
      }
      continue;
    }
    btLineBuffer += c;
    if (btLineBuffer.length() > 280) {
      btLineBuffer.remove(0, btLineBuffer.length() - 280);
    }
  }
}

bool sim900FtpUploadFile(const char* localPath, const String& remoteName) {
  File f = SPIFFS.open(localPath, FILE_READ);
  if (!f) {
    return false;
  }

  // SIM900 FTP setup
  modem.sendAT("+FTPCID=1");
  if (!waitForOk(5000L)) { f.close(); return false; }

  modem.sendAT("+FTPSERV=\"", FTP_HOST, "\"");
  if (!waitForOk(5000L)) { f.close(); return false; }

  modem.sendAT("+FTPUN=\"", FTP_USER, "\"");
  if (!waitForOk(5000L)) { f.close(); return false; }

  modem.sendAT("+FTPPW=\"", FTP_PASS, "\"");
  if (!waitForOk(5000L)) { f.close(); return false; }

  modem.sendAT("+FTPPATH=\"", FTP_PATH, "\"");
  if (!waitForOk(5000L)) { f.close(); return false; }

  modem.sendAT("+FTPPUTNAME=\"", remoteName, "\"");
  if (!waitForOk(5000L)) { f.close(); return false; }

  modem.sendAT("+FTPPUT=1");
  if (modem.waitResponse(15000L) != 1) { f.close(); return false; }

  const size_t chunkSize = 512;
  uint8_t chunk[chunkSize];
  while (f.available()) {
    size_t n = f.read(chunk, chunkSize);
    if (n == 0) {
      break;
    }

    modem.sendAT("+FTPPUT=2,", (int)n);
    int r = modem.waitResponse(10000L, "DOWNLOAD", "OK");
    if (r != 1) {
      f.close();
      return false;
    }

    SerialAT.write(chunk, n);
    if (modem.waitResponse(15000L) != 1) {
      f.close();
      return false;
    }
  }

  f.close();
  modem.sendAT("+FTPPUT=2,0");
  waitForOk(10000L);
  return true;
}

bool uploadSegmentAndDelete(const char* localPath) {
  if (ackNumber < 0) {
    return false;
  }

  String remoteName = String("ack_") + String(ackNumber) + "_" + String(millis()) + ".wav";
  bool ok = sim900FtpUploadFile(localPath, remoteName);
  if (ok || FORCE_DELETE_ON_UPLOAD_FAILURE) {
    SPIFFS.remove(localPath);
  }
  return ok;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  randomSeed((uint32_t)esp_random());

  SerialAT.begin(115200, SERIAL_8N1, SIM900_RX_PIN, SIM900_TX_PIN);
  connectCellular();

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);

  btSerial.begin("DementiaAid-Embedded");

  lastAudioSegmentStartMs = millis();
}

void loop() {
  if (!modem.isNetworkConnected() || !modem.isGprsConnected()) {
    connectCellular();
  }

  if (!mqtt.connected()) {
    connectMqtt();
  }
  mqtt.loop();

  handleBluetoothTranscriptInput();

  sendHandshakeIfNeeded();

  unsigned long now = millis();

  if (now - lastSensorMs >= SENSOR_INTERVAL_MS) {
    lastSensorMs = now;
    publishSensorFrame();
  }

  if (ackNumber >= 0 && now - lastAudioSegmentStartMs >= AUDIO_SEGMENT_MS) {
    lastAudioSegmentStartMs = now;

    const char* tempPath = "/audio_5s.wav";
    if (recordFiveSecondsToSpiffs(tempPath)) {
      uploadSegmentAndDelete(tempPath);
    }
  }

  delay(2);
}
