/* Coordinates temperature, tamper, and vibration readings so main.cpp does not need to control each sensor separately. */
#include "sensor_manager.h"
#include "tamper_detector.h"
#include "temperature_sensor.h"
#include "vibration_sensor.h"
#include <Arduino.h>

void initSensors()
{
    randomSeed(static_cast<unsigned long>(micros()));
    initTemperatureSensor();
    initTamperDetector();
    initVibrationSensor();
}

SensorData readSensors()
{
    return {
        readTemperatureC(),
        tamperDetected(),
        vibrationDetected()};
}