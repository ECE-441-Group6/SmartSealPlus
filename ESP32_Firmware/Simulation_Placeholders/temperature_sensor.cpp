/* Generates a simulated container temperature until the DS18B20 is connected. */
#include <Arduino.h>
#include "temperature_sensor.h"

void initTemperatureSensor()
{
}

float readTemperatureC()
{
    return 1.0f + static_cast<float>(random(0, 901)) / 100.0f;
}
