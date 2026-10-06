/* Coordinates temperature, tamper, and vibration readings so main.cpp does not need to control each sensor separately. */
#include "sensor_manager.h"

void initSensors()
{
    // initialize sensors here
}

SensorData readSensors()
{
    SensorData data;

    // Dummy values for testing
    data.temperature = 4.5;
    data.tamper = false;
    data.vibration = false;

    return data;
}