#include <Arduino.h>
#include <SD.h>
#include <SPI.h>

#include "app_config.h"

namespace {
#if defined(HSPI)
constexpr uint8_t kSdSpiHost = HSPI;
#elif defined(FSPI)
constexpr uint8_t kSdSpiHost = FSPI;
#else
constexpr uint8_t kSdSpiHost = 0;
#endif

SPIClass sdSpi(kSdSpiHost);

[[noreturn]] void fatalLoop(const char* msg) {
  while (true) {
    Serial.printf("[SDTEST] %s\n", msg);
    delay(1000);
  }
}

const char* cardTypeToText(uint8_t type) {
  switch (type) {
    case CARD_MMC:
      return "MMC";
    case CARD_SD:
      return "SDSC";
    case CARD_SDHC:
      return "SDHC/SDXC";
    default:
      return "UNKNOWN";
  }
}

bool mountSd() {
  Serial.printf("[SDTEST] SPI host=%u SCK=%d MISO=%d MOSI=%d CS=%d\n",
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

  sdSpi.begin(cfg::PIN_SD_SCK, cfg::PIN_SD_MISO, cfg::PIN_SD_MOSI, cfg::PIN_SD_CS);

  const uint32_t speeds[] = {
      400000U,
      1000000U,
      cfg::SD_SPI_HZ,
      10000000U,
  };

  for (size_t i = 0; i < (sizeof(speeds) / sizeof(speeds[0])); ++i) {
    const uint32_t hz = speeds[i];
    Serial.printf("[SDTEST] Mount try at %lu Hz...\n", static_cast<unsigned long>(hz));
    if (SD.begin(cfg::PIN_SD_CS, sdSpi, hz)) {
      Serial.printf("[SDTEST] Mounted at %lu Hz\n", static_cast<unsigned long>(hz));
      return true;
    }
    SD.end();
    delay(120);
  }

  Serial.println("[SDTEST] Mount failed at all SPI speeds");
  return false;
}

bool blockReadWriteCheck() {
  uint8_t tx[512];
  uint8_t rx[512];

  for (size_t i = 0; i < sizeof(tx); ++i) {
    tx[i] = static_cast<uint8_t>(i & 0xFF);
  }

  File f = SD.open("/sd_probe.bin", FILE_WRITE);
  if (!f) {
    Serial.println("[SDTEST] Cannot open /sd_probe.bin for write");
    return false;
  }

  const size_t wrote = f.write(tx, sizeof(tx));
  f.close();
  if (wrote != sizeof(tx)) {
    Serial.printf("[SDTEST] Write size mismatch: %u/%u\n",
                  static_cast<unsigned>(wrote),
                  static_cast<unsigned>(sizeof(tx)));
    return false;
  }

  f = SD.open("/sd_probe.bin", FILE_READ);
  if (!f) {
    Serial.println("[SDTEST] Cannot open /sd_probe.bin for read");
    return false;
  }

  const size_t readLen = f.read(rx, sizeof(rx));
  f.close();
  if (readLen != sizeof(rx)) {
    Serial.printf("[SDTEST] Read size mismatch: %u/%u\n",
                  static_cast<unsigned>(readLen),
                  static_cast<unsigned>(sizeof(rx)));
    return false;
  }

  for (size_t i = 0; i < sizeof(tx); ++i) {
    if (tx[i] != rx[i]) {
      Serial.printf("[SDTEST] Data mismatch at index %u\n", static_cast<unsigned>(i));
      return false;
    }
  }

  Serial.println("[SDTEST] 512-byte write/read verification OK");
  return true;
}

void appendHeartbeat() {
  File f = SD.open("/sd_test.txt", FILE_APPEND);
  if (!f) {
    Serial.println("[SDTEST] Cannot open /sd_test.txt for append");
    return;
  }

  f.printf("uptime_ms=%lu\n", static_cast<unsigned long>(millis()));
  f.close();

  f = SD.open("/sd_test.txt", FILE_READ);
  if (!f) {
    Serial.println("[SDTEST] Cannot open /sd_test.txt for read");
    return;
  }

  Serial.printf("[SDTEST] /sd_test.txt size=%u bytes\n", static_cast<unsigned>(f.size()));
  f.close();
}

}  // namespace

void setup() {
  Serial.begin(115200);
  const uint32_t startWait = millis();
  while (!Serial && (millis() - startWait < 4000U)) {
    delay(10);
  }
  delay(300);

  Serial.println();
  Serial.println("=== SD Module Standalone Test ===");

  if (!mountSd()) {
    fatalLoop("Mount failed at all SPI speeds");
  }

  const uint8_t type = SD.cardType();
  if (type == CARD_NONE) {
    fatalLoop("Card not detected after mount");
  }

  Serial.printf("[SDTEST] Card type: %s\n", cardTypeToText(type));
  Serial.printf("[SDTEST] Card size: %llu MB\n", SD.cardSize() / (1024ULL * 1024ULL));
  Serial.printf("[SDTEST] Total: %llu MB, Used: %llu MB\n",
                SD.totalBytes() / (1024ULL * 1024ULL),
                SD.usedBytes() / (1024ULL * 1024ULL));

  if (!blockReadWriteCheck()) {
    Serial.println("[SDTEST] Block check FAILED");
  }

  appendHeartbeat();
  Serial.println("[SDTEST] Setup complete. Periodic append every 5s.");
}

void loop() {
  static uint32_t last = 0;
  const uint32_t now = millis();

  if (now - last >= 5000U) {
    last = now;
    appendHeartbeat();
  }

  delay(50);
}
