/* Main ESP32 program. Initializes sensors, BLE, buzzer/LED, then repeatedly reads sensors and broadcasts status. */
#include "sensor_manager.h"
#include "ble_advertising.h"
#include "alert_manager.h"

void setup()
{
    // Start serial logging and initialize each hardware subsystem once.
    Serial.begin(115200);

    initSensors();
    initBLE();
    initAlerts();

    Serial.println("SmartSeal Started");
}

void loop()
{
    // Read the sensors, publish the current state, then run local alerts.
    SensorData data = readSensors();

    updateBLEAdvertisement(data);

    processAlerts(data);

    // Limit broadcasts and sensor checks to approximately once per second.
    delay(1000);
}