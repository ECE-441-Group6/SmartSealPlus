#pragma once

#include <Arduino.h>

constexpr int RECORD_BUTTON_PIN = D6;
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
constexpr unsigned long SERIAL_INTERVAL_MS = 5000;
constexpr unsigned long BLE_TRANSMISSION_INTERVAL_MS = 100;
constexpr unsigned long DEBOUNCE_MS = 40;
constexpr uint32_t VIBRATION_SAMPLE_INTERVAL_US = 1000;
constexpr uint16_t VIBRATION_CALIBRATION_SAMPLES = 1000;
constexpr uint16_t VIBRATION_THRESHOLD_COUNTS = 100;
constexpr float VIBRATION_NOISE_MULTIPLIER = 4.0f;
constexpr uint8_t VIBRATION_CONFIRMATION_SAMPLES = 3;
constexpr unsigned long VIBRATION_CONFIRMATION_WINDOW_MS = 20;
constexpr unsigned long VIBRATION_REARM_QUIET_MS = 100;

constexpr bool SERIAL_PLOTTER_MODE = true;
