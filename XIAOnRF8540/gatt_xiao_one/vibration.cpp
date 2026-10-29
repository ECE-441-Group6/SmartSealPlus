#include "Vibration.h"
#include <Arduino.h>

static const int VIBRATION_PIN = A2;
static const float ADC_MAX_VALUE = 4095.0f;
static const float ADC_REFERENCE_MV = 3050.0f;

void vibrationBegin() {
    pinMode(VIBRATION_PIN, INPUT);
}

int readVibrationADC() {
    return analogRead(VIBRATION_PIN);
}

float vibrationADCToVolts(int adcValue) {
    return ((float)adcValue / ADC_MAX_VALUE) *
           (ADC_REFERENCE_MV / 1000.0f);
}