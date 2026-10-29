#pragma once

#include <Arduino.h>

void initializeBle();
bool sendSensorPacket(
  uint32_t sealId,
  uint32_t eventSequence,
  float temperature,
  bool tamper,
  float vibration
);
void sendHeartbeat();
bool getAcknowledgment(uint32_t *sequence);
