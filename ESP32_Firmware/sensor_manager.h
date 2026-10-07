/* Defines the shared sensor snapshot and declares the sensor manager API. */
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