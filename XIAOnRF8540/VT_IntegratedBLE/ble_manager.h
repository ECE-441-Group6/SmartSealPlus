#pragma once

#include <Arduino.h>

void initializeBle();
void sendBleMessage(const char *message);
void updateGatewayAdvertisement(float temperatureF, float vibrationVoltage);
bool waitForGatewayAcknowledgement();
bool isBleClientConnected();
