/* Controls the buzzer and LEDs when tampering, temperature problems, or other important events occur. */
#include "alert_manager.h"
#include <Arduino.h>

void initAlerts()
{
    Serial.println("Alerts initialized in serial-only simulation mode");
}

void processAlerts(SensorData data)
{
    if (data.tamper)
    {
        Serial.println("TAMPER ALERT");
    }

    if (data.temperature > 8)
    {
        Serial.println("TEMP ALERT");
    }

    if (data.vibration)
    {
        Serial.println("VIBRATION ALERT");
    }
}