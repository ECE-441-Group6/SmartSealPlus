#pragma once

#include <Arduino.h>

void initializeBle();
void sendBleMessage(const char *message);
void updateGatewayAdvertisement(float temperatureC, float vibrationVoltage);
void repeatGatewayAdvertisement(float temperatureC, float vibrationVoltage);
bool waitForGatewayAcknowledgement();
bool isBleClientConnected();
