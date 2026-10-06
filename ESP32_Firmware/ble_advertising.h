/* Declares BLE advertising functions. */
#ifndef BLE_ADVERTISING_H
#define BLE_ADVERTISING_H

#include "sensor_manager.h"

void initBLE();
void updateBLEAdvertisement(SensorData data);

#endif