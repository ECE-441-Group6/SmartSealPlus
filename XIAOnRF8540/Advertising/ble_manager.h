#pragma once

#include <Arduino.h>

void initializeBle();
void stopEncryptedAdvertising();
bool createEncryptedPacket(
  float temperatureC,
  bool vibrationDetected,
  uint8_t movementCode,
  uint8_t *packet
);
void startEncryptedAdvertising(const uint8_t *packet);
