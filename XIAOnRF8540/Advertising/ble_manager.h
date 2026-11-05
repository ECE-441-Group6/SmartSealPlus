#pragma once

#include <Arduino.h>

bool initializeBle();
bool updateGatewayAdvertisement(
  float temperatureC,
  bool vibrationDetected
);
