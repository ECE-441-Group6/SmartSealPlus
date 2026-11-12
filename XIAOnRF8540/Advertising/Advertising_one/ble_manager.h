#pragma once

#include <Arduino.h>

void initializeBle();
bool updateGatewayAdvertisement(
  float temperatureC,
  bool vibrationDetected
);

//For accelerometer detection,can comment out when not using accelerometer
bool updateGatewayAdvertisement(
  float temperatureC,
  bool vibrationDetected,
  uint8_t movementType
);