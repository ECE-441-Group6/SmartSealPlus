#pragma once

#include <Arduino.h>

void initializeBle();
bool updateGatewayAdvertisement(
  float temperatureC,
  bool vibrationDetected
);
