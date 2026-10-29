#include <Arduino.h>

#include <math.h>
#include <stdio.h>

#include "ble_manager.h"
#include "config.h"
#include "sensor_manager.h"

namespace {
bool recording = false;
int lastButtonReading = HIGH;
int stableButtonState = HIGH;
unsigned long lastDebounceTime = 0;
unsigned long lastTempSampleTime = 0;
unsigned long lastSerialPrintTime = 0;
unsigned long lastBleTransmissionTime = 0;
uint32_t nextVibrationSampleMicros = 0;
float latestTemperatureC = NAN;
bool vibrationCalibrating = false;
bool vibrationEventPending = false;
uint16_t vibrationCalibrationCount = 0;
double vibrationCalibrationMean = 0.0;
double vibrationCalibrationM2 = 0.0;
float vibrationBaseline = 0.0f;
float vibrationNoiseStdDev = 0.0f;
unsigned long vibrationWindowStartTime = 0;
unsigned long vibrationLastAboveTime = 0;
uint8_t vibrationThresholdCount = 0;
bool vibrationEventActive = false;

void startVibrationCalibration() {
  vibrationCalibrating = true;
  vibrationEventPending = false;
  vibrationCalibrationCount = 0;
  vibrationCalibrationMean = 0.0;
  vibrationCalibrationM2 = 0.0;
  vibrationBaseline = 0.0f;
  vibrationNoiseStdDev = 0.0f;
  vibrationWindowStartTime = millis();
  vibrationLastAboveTime = vibrationWindowStartTime;
  vibrationThresholdCount = 0;
  vibrationEventActive = false;
  nextVibrationSampleMicros = micros();
  Serial.println("Vibration baseline calibration started; keep the seal still.");
}

void printPlotterValues(float temperatureC, float vibrationVoltage) {
  if (!SERIAL_PLOTTER_MODE) {
    return;
  }
  Serial.print("Temp_C:");
  if (isfinite(temperatureC)) {
    Serial.print(temperatureC, 2);
  } else {
    Serial.print("nan");
  }
  Serial.print(" Vibration_V:");
  Serial.println(vibrationVoltage, 1);
}

void startRecording() {
  if (recording) {
    return;
  }
  recording = true;
  const unsigned long now = millis();
  lastTempSampleTime = now - TEMP_INTERVAL_MS;
  lastSerialPrintTime = now - SERIAL_INTERVAL_MS;
  lastBleTransmissionTime = now - ADVERTISEMENT_INTERVAL_MS;
  latestTemperatureC = NAN;
  startVibrationCalibration();
  Serial.println("Recording started.");
}

void stopRecording() {
  if (!recording) {
    return;
  }
  recording = false;
  Serial.println("Recording stopped.");
}

void updateButton(unsigned long now) {
  const int reading = digitalRead(RECORD_BUTTON_PIN);
  if (reading != lastButtonReading) {
    lastDebounceTime = now;
    lastButtonReading = reading;
  }
  if (now - lastDebounceTime < DEBOUNCE_MS ||
      reading == stableButtonState) {
    return;
  }
  stableButtonState = reading;
  if (stableButtonState == LOW) {
    recording ? stopRecording() : startRecording();
  }
}

void sampleTemperature(unsigned long now) {
  if (now - lastTempSampleTime < TEMP_INTERVAL_MS) {
    return;
  }
  lastTempSampleTime = now;
  const TemperatureReading reading = readTemperature();
  if (reading.valid) {
    latestTemperatureC = reading.celsius;
  }
}

void sampleVibration() {
  const uint32_t nowMicros = micros();
  if (static_cast<int32_t>(nowMicros - nextVibrationSampleMicros) < 0) {
    return;
  }
  nextVibrationSampleMicros =
    nowMicros + VIBRATION_SAMPLE_INTERVAL_US;

  const int vibrationADC = analogRead(VIBRATION_PIN);
  const unsigned long now = millis();
  if (vibrationCalibrating) {
    ++vibrationCalibrationCount;
    const double delta = vibrationADC - vibrationCalibrationMean;
    vibrationCalibrationMean +=
      delta / vibrationCalibrationCount;
    const double deltaAfterMean =
      vibrationADC - vibrationCalibrationMean;
    vibrationCalibrationM2 += delta * deltaAfterMean;
    if (vibrationCalibrationCount >= VIBRATION_CALIBRATION_SAMPLES) {
      vibrationCalibrating = false;
      vibrationBaseline = static_cast<float>(vibrationCalibrationMean);
      vibrationNoiseStdDev = static_cast<float>(
        sqrt(vibrationCalibrationM2 / vibrationCalibrationCount)
      );
      vibrationWindowStartTime = now;
      vibrationLastAboveTime = now;
      vibrationThresholdCount = 0;
      Serial.print("Vibration calibration complete. Baseline ADC: ");
      Serial.print(vibrationBaseline, 1);
      Serial.print(", noise standard deviation ADC: ");
      Serial.println(vibrationNoiseStdDev, 1);
    }
    return;
  }

  if (now - vibrationWindowStartTime >=
      VIBRATION_CONFIRMATION_WINDOW_MS) {
    vibrationWindowStartTime = now;
    vibrationThresholdCount = 0;
  }

  const float deviation =
    fabsf(static_cast<float>(vibrationADC) - vibrationBaseline);
  const float vibrationThreshold = fmaxf(
    static_cast<float>(VIBRATION_THRESHOLD_COUNTS),
    vibrationNoiseStdDev * VIBRATION_NOISE_MULTIPLIER
  );
  const bool aboveThreshold = deviation >= vibrationThreshold;
  if (aboveThreshold) {
    vibrationLastAboveTime = now;
  } else if (vibrationEventActive &&
             now - vibrationLastAboveTime >=
               VIBRATION_REARM_QUIET_MS) {
    vibrationEventActive = false;
  }

  if (aboveThreshold &&
      vibrationThresholdCount < VIBRATION_CONFIRMATION_SAMPLES) {
    ++vibrationThresholdCount;
    if (vibrationThresholdCount >= VIBRATION_CONFIRMATION_SAMPLES &&
        !vibrationEventActive) {
      vibrationEventActive = true;
      vibrationEventPending = true;
      Serial.print("Vibration event detected. ADC: ");
      Serial.print(vibrationADC);
      Serial.print(", baseline: ");
      Serial.print(vibrationBaseline, 1);
      Serial.print(", deviation: ");
      Serial.println(deviation, 1);
    }
  }

  if (now - lastSerialPrintTime >= SERIAL_INTERVAL_MS) {
    lastSerialPrintTime = now;
    printPlotterValues(
      latestTemperatureC,
      static_cast<float>(vibrationADC) * ADC_REFERENCE_VOLTAGE / ADC_MAX
    );
  }

  if (now - lastBleTransmissionTime >=
      ADVERTISEMENT_INTERVAL_MS) {
    lastBleTransmissionTime = now;
    if (updateGatewayAdvertisement(
          latestTemperatureC,
          vibrationEventPending
        )) {
      vibrationEventPending = false;
    }
  }
}
}

void setup() {
  Serial.begin(115200);
  const unsigned long serialStart = millis();
  while (!Serial && millis() - serialStart < 5000) {
    delay(10);
  }
  Serial.println();
  Serial.println("Starting VT_IntegratedBLE...");
  pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);
  pinMode(TEMP_PIN, INPUT);
  pinMode(VIBRATION_PIN, INPUT);
  analogReadResolution(12);
  Serial.println("Initializing BLE...");
  initializeBle();
  Serial.println("XIAO nRF52840 recorder ready.");
  Serial.println("Press the record button on D6 to start sampling.");
}

void loop() {
  const unsigned long now = millis();
  updateButton(now);
  if (recording) {
    sampleVibration();
  } else {
    static unsigned long lastIdleMessage = 0;
    if (now - lastIdleMessage >= 5000) {
      lastIdleMessage = now;
      Serial.println("Idle: waiting for record button.");
    }
  }
  sampleTemperature(millis());
}
