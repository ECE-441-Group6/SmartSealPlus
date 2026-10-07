/* Creates and periodically broadcasts the BLE advertisement containing SmartSeal data. */
#include "ble_advertising.h"
#include <Arduino.h>

void initBLE()
{
    // TODO: initialize the ESP32 BLE stack, service, and advertising payload.
    Serial.println("BLE Initialized");
}

void updateBLEAdvertisement(SensorData data)
{
    // This output is a placeholder for a real BLE advertisement update.
    Serial.print("Advertising: ");

    Serial.print(data.temperature);
    Serial.print(" ");

    Serial.print(data.tamper);
    Serial.print(" ");

    Serial.println(data.vibration);

    // TODO: encode seal ID and sensor values, then start/restart advertising.
}