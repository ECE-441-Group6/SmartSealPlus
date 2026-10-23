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
unsigned long lastVibrationSampleTime = 0;
unsigned long lastAdvertisementTime = 0;
float latestTemperatureF = NAN;

void printPlotterValues(float temperatureF, float vibrationVoltage) {
  if (!SERIAL_PLOTTER_MODE) {
    return;
  }
  Serial.print("Temp_F:");
  if (isfinite(temperatureF)) {
    Serial.print(temperatureF, 2);
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
  lastVibrationSampleTime = now - VIBRATION_INTERVAL_MS;
  lastAdvertisementTime = now - ADVERTISEMENT_INTERVAL_MS;
  latestTemperatureF = NAN;
  Serial.println("Recording started.");
  sendBleMessage("START\n");
}

void stopRecording() {
  if (!recording) {
    return;
  }
  recording = false;
  Serial.println("Recording stopped.");
  sendBleMessage("STOP\n");
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
    latestTemperatureF = reading.fahrenheit;
  }
}

void sampleVibration(unsigned long now) {
  if (now - lastVibrationSampleTime < VIBRATION_INTERVAL_MS) {
    return;
  }
  lastVibrationSampleTime = now;

  int vibrationADC = 0;
  const float vibrationVoltage = readVibrationVoltage(vibrationADC);
  printPlotterValues(latestTemperatureF, vibrationVoltage);

  char packet[21];
  const int packetLength = snprintf(
    packet,
    sizeof(packet),
    "D,%lu,%d,%.1f",
    now,
    vibrationADC,
    latestTemperatureF
  );
  if (packetLength > 0 && packetLength <= 20) {
    sendBleMessage(packet);
  }

  if (now - lastAdvertisementTime >= ADVERTISEMENT_INTERVAL_MS) {
    lastAdvertisementTime = now;
    updateGatewayAdvertisement(latestTemperatureF, vibrationADC);
  }
}
}

void setup() {
  Serial.begin(115200);
  const unsigned long serialStart = millis();
  while (!Serial && millis() - serialStart < 5000) {
    delay(10);
  }
  delay(250);
  Serial.println();
  Serial.println("Starting VT_IntegratedBLE...");
  pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);
  pinMode(TEMP_PIN, INPUT);
  pinMode(VIBRATION_PIN, INPUT);
  analogReadResolution(12);
  Serial.println("Initializing BLE...");
  initializeBle();
  Serial.println("XIAO nRF52840 recorder ready.");
  Serial.println("Press the record button on D4 to start sampling.");
}

void loop() {
  const unsigned long now = millis();
  updateButton(now);
  if (!recording) {
    static unsigned long lastIdleMessage = 0;
    if (now - lastIdleMessage >= 5000) {
      lastIdleMessage = now;
      Serial.println("Idle: waiting for record button.");
    }
    delay(1);
    return;
  }
  sampleTemperature(millis());
  sampleVibration(millis());
  delay(1);
}
