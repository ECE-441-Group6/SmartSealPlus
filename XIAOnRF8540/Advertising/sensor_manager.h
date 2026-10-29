#pragma once

#include <Arduino.h>

struct TemperatureReading {
  int adcValue;
  float voltage;
  float resistance;
  float celsius;
  float fahrenheit;
  bool valid;
};

TemperatureReading readTemperature();
float readVibrationVoltage(int &adcValue);
