/* Declares BLE setup and payload-update functions used by main.cpp. */
#ifndef BLE_ADVERTISING_H
#define BLE_ADVERTISING_H

#include "sensor_manager.h"

#define SMARTSEAL_DEVICE_NAME "SmartSeal-01"
#define SMARTSEAL_SEAL_ID 1
#define SMARTSEAL_TRANSMIT_INTERVAL_MS 5000

void initBLE();
void updateBLEAdvertisement(SensorData data);

#endif