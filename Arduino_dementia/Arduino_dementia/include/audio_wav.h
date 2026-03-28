#pragma once

#include <Arduino.h>
#include <FS.h>

namespace audiowav {

void writeWavHeader(File& file, uint32_t sampleRate, uint32_t numSamples);
bool initBluetoothMicI2S(uint32_t sampleRate, int pinBclk, int pinWs, int pinDin);
void shutdownBluetoothMicI2S();
bool recordBluetoothMicSegment(const char* fullPath, uint16_t sampleRate, uint8_t seconds);

}  // namespace audiowav
