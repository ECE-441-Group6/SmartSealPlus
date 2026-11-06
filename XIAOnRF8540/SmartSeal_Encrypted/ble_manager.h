#pragma once

#include <Arduino.h>

void initializeBle();
bool createEncryptedPacket(
  float temperatureC,
  bool vibrationDetected,
  uint8_t *packet
);
void startEncryptedAdvertising(const uint8_t *packet);
