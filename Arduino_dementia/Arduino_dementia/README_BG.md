# ESP32-S3 Dementia Assist - wiring and run guide

## 1) Wiring (ESP32-S3)

### SIM900A (UART)
- ESP32 `GPIO15` (TX) -> SIM900A `RX` (through level shift or resistor divider)
- ESP32 `GPIO16` (RX) <- SIM900A `TX`
- ESP32 `GPIO21` -> SIM900A `PWRKEY` (optional, through transistor)
- Common `GND`

### NEO-6M GPS (UART)
- ESP32 `GPIO17` (TX) -> GPS `RX`
- ESP32 `GPIO18` (RX) <- GPS `TX`
- ESP32 `GPIO38` -> GPS `EN` (optional power control)

### MPU6050 (I2C)
- ESP32 `GPIO8` -> `SDA`
- ESP32 `GPIO9` -> `SCL`

### SD module (SPI)
- ESP32 `GPIO40` -> `SCK`
- ESP32 `GPIO42` -> `MOSI`
- ESP32 `GPIO41` <- `MISO`
- ESP32 `GPIO39` -> `CS`

### Bluetooth headset microphone (through BT audio bridge module with I2S output)
- ESP32 `GPIO4` <- bridge `BCLK`
- ESP32 `GPIO5` <- bridge `WS/LRCLK`
- ESP32 `GPIO6` <- bridge `DOUT/PCM_OUT`

Important:
- ESP32-S3 does not support Classic Bluetooth HFP client for direct headset mic capture.
- Standard Bluetooth headset microphone must be terminated by an external BT audio bridge module.
- Headset pairing is done by the bridge module firmware, not by ESP32-S3.

## 2) Power notes

- SIM900A needs separate stable power around 4.0V with up to 2A peak.
- Do not power SIM900A directly from weak 5V USB rails.
- Keep all grounds common.

## 3) Configure credentials

Edit `include/app_config.h`:
- APN: `APN`, `GPRS_USER`, `GPRS_PASS`
- MQTT: host/port/user/pass/topics
- FTP: host/port/user/pass
- identity: `PATIENT_USERNAME`, `PATIENT_ROLE`

## 4) Security flags

In `include/app_config.h`:
- `REQUIRE_SECURE_LINKS = true` will block startup unless secure links are active.
- For SIM900A defaults are `MODEM_SUPPORTS_TLS = false`, `MQTT_USE_TLS = false`, `FTP_USE_TLS = false`.

## 5) Runtime behavior

- On boot the device validates config and security flags.
- It opens GPRS and MQTT, sends init JSON:
  - `username`
  - `deviceId` (random alphanumeric)
  - `role` (`user` or `caregiver`)
- Waits for ACK (`ack` or `acknowledgmentNumber`) from MQTT ACK topic.
- Uses ACK to initialize FTP session directory.
- Records 5-second WAV segments continuously from Bluetooth headset mic (I2S bridge) to SD.
- Uploads segments over FTP and deletes local files after successful upload.
- Reads IMU+GPS every 50 ms, sends telemetry over MQTT.
- If no movement for `STATIONARY_TIMEOUT_MS`, GPS is disabled for power saving.

## 6) Main source files

- `src/main.cpp` - entrypoint only
- `src/dementia_device.cpp` + `include/dementia_device.h` - app workflow/tasks/MQTT/IMU/GPS
- `src/ftp_uploader.cpp` + `include/ftp_uploader.h` - FTP control+data channel upload
- `src/audio_wav.cpp` + `include/audio_wav.h` - WAV writer and 5-second recording helper
- `include/app_config.h` - credentials, pins, thresholds, timing

## 7) Standalone SD test firmware

- Test-only file: `src/sd_module_test.cpp`
- PlatformIO env: `esp32s3_sdtest`
- Build + upload:
  - `pio run -e esp32s3_sdtest -t upload`
- Monitor:
  - `pio device monitor -e esp32s3_sdtest`
