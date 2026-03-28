#include <Arduino.h>

#include "dementia_device.h"

static DementiaDevice device;

void setup() {
  device.begin();
}

void loop() {
  device.loop();
}
