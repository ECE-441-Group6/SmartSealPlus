#include "sensor_manager.h"

#include <math.h>

#include "config.h"

namespace {
float vibrationBaseline = 0.0f;
}

// Assumption:
// Thermistor connected to 3.3V.
// Fixed resistor connected from ADC to GND.

float readTemperatureC() {

    int raw = analogRead(TEMP_PIN);

    if (raw <= 0 || raw >= ADC_MAX) {
        return NAN;
    }

    float resistance =
        R_BOTTOM_OHMS *
        ((float)ADC_MAX / (float)raw - 1.0f);

    if (resistance <= 0.0f) {
        return NAN;
    }

    float inverseTemperature =
        (1.0f / T25_K) +
        (log(resistance / R25) / BETA);

    return (1.0f / inverseTemperature) - 273.15f;
}


void calibrateVibrationSensor() {

    Serial.println("Calibrating vibration baseline...");

    uint32_t total = 0;

    constexpr uint16_t SAMPLES = 1000;

    for (uint16_t i = 0; i < SAMPLES; i++) {

        total += analogRead(VIBRATION_PIN);

        delay(1);
    }

    vibrationBaseline =
        (float)total / SAMPLES;

    Serial.print("Vibration baseline: ");
    Serial.println(vibrationBaseline);
}


VibrationReading detectVibration() {

    constexpr uint16_t THRESHOLD = 100;
    constexpr uint8_t REQUIRED_HITS = 3;
    constexpr uint8_t TOTAL_SAMPLES = 20;

    uint8_t hits = 0;
    VibrationReading result = {};

    for (uint8_t i = 0; i < TOTAL_SAMPLES; i++) {

        int reading = analogRead(VIBRATION_PIN);

        const float difference =
            fabs((float)reading - vibrationBaseline);

        result.adcValue = reading;
        result.baseline = vibrationBaseline;
        result.deviation = difference;
        result.voltage =
            ((float)reading / ADC_MAX) * ADC_REFERENCE_VOLTAGE;

        if (difference > THRESHOLD) {
            hits++;
        }

        if (hits >= REQUIRED_HITS) {
            result.detected = true;
            return result;
        }

        delay(1);
    }

    return result;
}
