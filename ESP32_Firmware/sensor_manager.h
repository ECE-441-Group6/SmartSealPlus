/* Declares the functions used to access all SmartSeal sensors. */
#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

struct SensorData
{
    float temperature;
    bool tamper;
    bool vibration;
};

void initSensors();
SensorData readSensors();

#endif