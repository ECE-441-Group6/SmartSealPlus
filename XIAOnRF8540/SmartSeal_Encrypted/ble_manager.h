#pragma once

#include <Arduino.h>

// Initialize the radio, construct authenticated sensor packets, and publish
// those packets in BLE manufacturer data (no GATT connection is used).
void initializeBle();
void stopEncryptedAdvertising();
bool createEncryptedPacket(
  float temperatureC,
  float vibrationMagnitudeVolts,
  uint8_t movementCode,
  uint8_t *packet
);
void startEncryptedAdvertising(const uint8_t *packet);
