#pragma once

#include <Arduino.h>

void initializeBle();
void sendBleMessage(const char *message);
bool updateGatewayAdvertisement(float temperatureC, bool vibrationDetected);
bool isBleClientConnected();
