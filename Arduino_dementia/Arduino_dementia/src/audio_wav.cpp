#include "audio_wav.h"

#include <SD.h>
#include <cstring>
#include <driver/i2s.h>

namespace {

constexpr i2s_port_t kI2sPort = I2S_NUM_0;
bool g_i2sInitialized = false;

}  // namespace

namespace audiowav {

void writeWavHeader(File& file, uint32_t sampleRate, uint32_t numSamples) {
  const uint32_t dataSize = numSamples * sizeof(int16_t);
  const uint32_t fileSize = 36 + dataSize;
  const uint32_t fmtChunkSize = 16;
  const uint16_t audioFormat = 1;
  const uint16_t channels = 1;
  const uint32_t byteRate = sampleRate * channels * sizeof(int16_t);
  const uint16_t blockAlign = channels * sizeof(int16_t);
  const uint16_t bitsPerSample = 16;

  file.write(reinterpret_cast<const uint8_t*>("RIFF"), 4);
  file.write(reinterpret_cast<const uint8_t*>(&fileSize), 4);
  file.write(reinterpret_cast<const uint8_t*>("WAVE"), 4);
  file.write(reinterpret_cast<const uint8_t*>("fmt "), 4);
  file.write(reinterpret_cast<const uint8_t*>(&fmtChunkSize), 4);
  file.write(reinterpret_cast<const uint8_t*>(&audioFormat), 2);
  file.write(reinterpret_cast<const uint8_t*>(&channels), 2);
  file.write(reinterpret_cast<const uint8_t*>(&sampleRate), 4);
  file.write(reinterpret_cast<const uint8_t*>(&byteRate), 4);
  file.write(reinterpret_cast<const uint8_t*>(&blockAlign), 2);
  file.write(reinterpret_cast<const uint8_t*>(&bitsPerSample), 2);
  file.write(reinterpret_cast<const uint8_t*>("data"), 4);
  file.write(reinterpret_cast<const uint8_t*>(&dataSize), 4);
}

bool initBluetoothMicI2S(uint32_t sampleRate, int pinBclk, int pinWs, int pinDin) {
  if (g_i2sInitialized) {
    i2s_set_clk(kI2sPort, sampleRate, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);
    return true;
  }

  i2s_config_t config = {};
  config.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX);
  config.sample_rate = sampleRate;
  config.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  config.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  config.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  config.dma_buf_count = 8;
  config.dma_buf_len = 256;
  config.use_apll = false;
  config.tx_desc_auto_clear = false;
  config.fixed_mclk = 0;

  const i2s_pin_config_t pins = {
      .mck_io_num = I2S_PIN_NO_CHANGE,
      .bck_io_num = pinBclk,
      .ws_io_num = pinWs,
      .data_out_num = I2S_PIN_NO_CHANGE,
      .data_in_num = pinDin,
  };

  if (i2s_driver_install(kI2sPort, &config, 0, nullptr) != ESP_OK) {
    Serial.println("[AUDIO] I2S driver install failed");
    return false;
  }

  if (i2s_set_pin(kI2sPort, &pins) != ESP_OK) {
    Serial.println("[AUDIO] I2S pin config failed");
    i2s_driver_uninstall(kI2sPort);
    return false;
  }

  if (i2s_zero_dma_buffer(kI2sPort) != ESP_OK) {
    Serial.println("[AUDIO] I2S DMA clear failed");
    i2s_driver_uninstall(kI2sPort);
    return false;
  }

  g_i2sInitialized = true;
  Serial.println("[AUDIO] Bluetooth mic I2S initialized");
  return true;
}

void shutdownBluetoothMicI2S() {
  if (!g_i2sInitialized) {
    return;
  }
  i2s_driver_uninstall(kI2sPort);
  g_i2sInitialized = false;
}

bool recordBluetoothMicSegment(const char* fullPath, uint16_t sampleRate, uint8_t seconds) {
  if (!g_i2sInitialized) {
    Serial.println("[AUDIO] I2S not initialized");
    return false;
  }

  const uint32_t totalSamples = static_cast<uint32_t>(sampleRate) * seconds;
  const uint32_t totalBytes = totalSamples * sizeof(int16_t);

  File out = SD.open(fullPath, FILE_WRITE);
  if (!out) {
    Serial.printf("[AUDIO] Failed to open %s\n", fullPath);
    return false;
  }

  writeWavHeader(out, sampleRate, totalSamples);

  uint32_t bytesWritten = 0;
  uint8_t buffer[1024];

  while (bytesWritten < totalBytes) {
    const uint32_t remaining = totalBytes - bytesWritten;
    const size_t requested = (remaining < sizeof(buffer)) ? remaining : sizeof(buffer);

    size_t bytesRead = 0;
    if (i2s_read(kI2sPort, buffer, requested, &bytesRead, pdMS_TO_TICKS(250)) != ESP_OK) {
      Serial.println("[AUDIO] I2S read failed");
      out.close();
      return false;
    }

    if (bytesRead == 0) {
      memset(buffer, 0, requested);
      bytesRead = requested;
    }

    const size_t writtenNow = out.write(buffer, bytesRead);
    if (writtenNow != bytesRead) {
      Serial.println("[AUDIO] SD write failed");
      out.close();
      return false;
    }

    bytesWritten += bytesRead;
  }

  out.close();
  return true;
}

}  // namespace audiowav
