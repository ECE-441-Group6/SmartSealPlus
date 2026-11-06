#include "sensor_manager.h"
#include <math.h>
#include "config.h"
#include "accelerometer.h"


// ==================================================
// TEMPERATURE SENSOR
// ==================================================

TemperatureReading readTemperature() {
  TemperatureReading reading = {};
  reading.adcValue = analogRead(TEMP_PIN);
  reading.voltage = ((float)reading.adcValue / ADC_MAX) * VCC;

  if (reading.voltage <= 0.001f || reading.voltage >= VCC) {
    return reading;
  }

  reading.resistance =
    R_BOTTOM * (VCC - reading.voltage) / reading.voltage;

  if (reading.resistance <= 0.0f || !isfinite(reading.resistance)) {
    return reading;
  }

  const float temperatureK =
    1.0f / ((1.0f / T25_K) +
            (1.0f / BETA) * log(reading.resistance / R25));

  reading.celsius = temperatureK - 273.15f;
  reading.fahrenheit = reading.celsius * 9.0f / 5.0f + 32.0f;

  reading.valid =
    isfinite(reading.celsius) && isfinite(reading.fahrenheit);

  return reading;
}


// ==================================================
// VIBRATION SENSOR
// ==================================================

float readVibrationVoltage(int &adcValue) {
  adcValue = analogRead(VIBRATION_PIN);
  return ((float)adcValue / ADC_MAX) * ADC_REFERENCE_VOLTAGE;
}


// ==================================================
// ACCELEROMETER
// ==================================================

// Read the ADXL345 and analyze the acceleration change.
// Returns the movement type code.
uint8_t readAccelerometer() {

  detectMovement();
  analyzeMovement();

  return getMovementCode();
}