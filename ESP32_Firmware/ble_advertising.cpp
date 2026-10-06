/* Creates and periodically broadcasts the BLE advertisement containing SmartSeal data. */
#include "ble_advertising.h"
#include <Arduino.h>

void initBLE()
{
    Serial.println("BLE Initialized");
}

void updateBLEAdvertisement(SensorData data)
{
    Serial.print("Advertising: ");

    Serial.print(data.temperature);
    Serial.print(" ");

    Serial.print(data.tamper);
    Serial.print(" ");

    Serial.println(data.vibration);

    // actual BLE code goes here later
}