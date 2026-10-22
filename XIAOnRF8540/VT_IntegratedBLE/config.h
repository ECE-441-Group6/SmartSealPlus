#pragma once

#include <Arduino.h>

constexpr int RECORD_BUTTON_PIN = D4;
constexpr int TEMP_PIN = A0;
constexpr int VIBRATION_PIN = A2;

constexpr float R25 = 10000.0f;
constexpr float BETA = 3950.0f;
constexpr float T25_K = 298.15f;
constexpr float R_BOTTOM = 1000.0f;
constexpr float VCC = 3.05f;
constexpr int ADC_MAX = 4095;
constexpr float ADC_REFERENCE_VOLTAGE = 3050.0f;

constexpr unsigned long TEMP_INTERVAL_MS = 5000;
constexpr unsigned long VIBRATION_INTERVAL_MS = 10;
constexpr unsigned long ADVERTISEMENT_INTERVAL_MS = 1000;
constexpr unsigned long DEBOUNCE_MS = 40;

constexpr bool SERIAL_PLOTTER_MODE = true;
