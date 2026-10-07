/* Coordinates temperature, tamper, and vibration readings so main.cpp does not need to control each sensor separately. */
#include "sensor_manager.h"

void initSensors()
{
    // TODO: configure the DS18B20, POF detector, and vibration sensor pins.
}

SensorData readSensors()
{
    SensorData data;

    // Simulation values keep the firmware structure testable before hardware
    // drivers are connected.
    data.temperature = 4.5;
    data.tamper = false;
    data.vibration = false;

    // TODO: replace these assignments with real sensor reads and filtering.
    return data;
}