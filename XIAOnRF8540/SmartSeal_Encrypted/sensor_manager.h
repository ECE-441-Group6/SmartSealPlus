#pragma once

#include <Arduino.h>

struct VibrationReading {
    bool detected;
    int adcValue;
    float baseline;
    float deviation;
    float voltage;
};

float readTemperatureC();
void calibrateVibrationSensor();
VibrationReading detectVibration();
