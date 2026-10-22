/* Generates a simulated vibration state until the sensor is connected. */
#include <Arduino.h>
#include "vibration_sensor.h"

void initVibrationSensor()
{
}

bool vibrationDetected()
{
    return random(0, 10) == 0;
}
