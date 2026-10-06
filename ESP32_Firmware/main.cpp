/* Main ESP32 program. Initializes sensors, BLE, buzzer/LED, then repeatedly reads sensors and broadcasts status. */
#include "sensor_manager.h"
#include "ble_advertising.h"
#include "alert_manager.h"

void setup()
{
    Serial.begin(115200);

    initSensors();
    initBLE();
    initAlerts();

    Serial.println("SmartSeal Started");
}

void loop()
{
    SensorData data = readSensors();

    updateBLEAdvertisement(data);

    processAlerts(data);

    delay(1000);
}