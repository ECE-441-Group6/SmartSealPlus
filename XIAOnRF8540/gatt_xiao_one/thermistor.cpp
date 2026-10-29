#include "Thermistor.h"
#include <Arduino.h>
#include <math.h>

// Thermistor connected to A0
static const int TEMP_PIN = A0;

// Thermistor parameters
static const float R25 = 10000.0f;
static const float BETA = 3950.0f;
static const float T25_K = 298.15f;

// Divider: 3.05 V -> NTC -> A0 -> 1 kΩ -> GND
static const float R_BOTTOM = 1000.0f;
static const float VCC = 3.05f;
static const float ADC_MAX_VALUE = 4095.0f;

void thermistorBegin() {
    pinMode(TEMP_PIN, INPUT);
}

bool readThermistor(float &temperatureC, float &temperatureF) {
    int adcValue = analogRead(TEMP_PIN);

    float voltage =
        ((float)adcValue / ADC_MAX_VALUE) * VCC;

    // Reject readings at either ADC extreme.
    if (voltage <= 0.001f || voltage >= VCC) {
        return false;
    }

    // Calculate NTC resistance for this divider arrangement.
    float resistance =
        R_BOTTOM * (VCC - voltage) / voltage;

    if (resistance <= 0.0f || !isfinite(resistance)) {
        return false;
    }

    // Beta equation.
    float temperatureK =
        1.0f /
        ((1.0f / T25_K) +
         (1.0f / BETA) * log(resistance / R25));

    temperatureC = temperatureK - 273.15f;
    temperatureF = temperatureC * 9.0f / 5.0f + 32.0f;

    return isfinite(temperatureC) &&
           isfinite(temperatureF);
}
