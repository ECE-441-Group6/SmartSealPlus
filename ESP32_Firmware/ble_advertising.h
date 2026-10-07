/* Declares BLE setup and payload-update functions used by main.cpp. */
#ifndef BLE_ADVERTISING_H
#define BLE_ADVERTISING_H

#include "sensor_manager.h"

void initBLE();
void updateBLEAdvertisement(SensorData data);

#endif