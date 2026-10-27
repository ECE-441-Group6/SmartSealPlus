/* Main ESP32 program. Initializes sensors, BLE, buzzer/LED, then repeatedly reads sensors and broadcasts status. */
#include <Arduino.h>
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
    if (isCriticalEvent(data))
    {
        for (int attempt = 0; attempt < SMARTSEAL_MAX_CRITICAL_RETRIES; ++attempt)
        {
            if (waitForGatewayAcknowledgement())
            {
                break;
            }
            repeatBLEAdvertisement(data);
        }
    }

    processAlerts(data);

    // Match the Raspberry Pi scan window so each scan receives one reading.
    delay(SMARTSEAL_TRANSMIT_INTERVAL_MS);
}