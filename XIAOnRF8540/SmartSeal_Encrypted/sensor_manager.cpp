#include "sensor_manager.h"

#include <math.h>

#include "config.h"

namespace {
float vibrationBaseline = 0.0f;
VibrationReading latestVibration = {};
uint8_t vibrationHits = 0;
bool vibrationLatched = false;
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

    latestVibration = {};
    vibrationHits = 0;
    vibrationLatched = false;

    Serial.print("Vibration baseline: ");
    Serial.println(vibrationBaseline);
}


void updateVibrationSensor() {

    constexpr uint16_t THRESHOLD = 20;
    constexpr uint8_t REQUIRED_HITS = 2;

    const int reading = analogRead(VIBRATION_PIN);
    const float difference =
        fabs((float)reading - vibrationBaseline);

    latestVibration.adcValue = reading;
    latestVibration.baseline = vibrationBaseline;
    latestVibration.deviation = difference;
    latestVibration.voltage =
        ((float)reading / ADC_MAX) * ADC_REFERENCE_VOLTAGE;

    if (difference > THRESHOLD) {
        if (vibrationHits < REQUIRED_HITS) {
            vibrationHits++;
        }
    } else {
        vibrationHits = 0;
    }

    if (vibrationHits >= REQUIRED_HITS) {
        vibrationLatched = true;
    }
}


VibrationReading detectVibration() {

    latestVibration.detected = vibrationLatched;
    vibrationLatched = false;

    return latestVibration;
}
