#pragma once

#include <Arduino.h>

void initializeBle();
void sendBleMessage(const char *message);
void updateGatewayAdvertisement(float temperatureF, int vibrationADC);
bool isBleClientConnected();
