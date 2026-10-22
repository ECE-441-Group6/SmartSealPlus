#include <ArduinoBLE.h>

// ============================================================
// XIAO PIN CONFIGURATION
// ============================================================

const int RECORD_BUTTON_PIN = D0;  // Button 1: start/stop
const int ADC_PIN           = D1;  // Analog sensor input
const int BUTTON2_PIN       = D2;  // Button 2: state logging

// Buttons connect between GPIO and GND.
// Both use internal pull-up resistors.

// ============================================================
// BLE CONFIGURATION
// ============================================================

const char* DEVICE_NAME = "ESP32_Recorder";

BLEService recordingService(
    "12345678-1234-1234-1234-1234567890ab"
);

BLEStringCharacteristic dataCharacteristic(
    "12345678-1234-1234-1234-1234567890ac",
    BLERead | BLENotify,
    20
);

// ============================================================
// RECORDING SETTINGS
// ============================================================

const unsigned long SAMPLE_INTERVAL_MS = 10; // Nominal 100 Hz
const unsigned long DEBOUNCE_MS = 40;

// ============================================================
// STATE VARIABLES
// ============================================================

bool recording = false;

int lastButtonReading = HIGH;
int stableButtonState = HIGH;

unsigned long lastDebounceTime = 0;
unsigned long lastSampleTime = 0;

// ============================================================
// SEND BLE MESSAGE
// ============================================================

void sendMessage(const char* message) {
  dataCharacteristic.writeValue(message);
}

// ============================================================
// START RECORDING
// ============================================================

void startRecording() {
  if (recording) return;

  recording = true;
  lastSampleTime = millis();

  Serial.println("Recording started");
  sendMessage("START\n");
}

// ============================================================
// STOP RECORDING
// ============================================================

void stopRecording() {
  if (!recording) return;

  recording = false;

  Serial.println("Recording stopped");
  sendMessage("STOP\n");
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);

  // Internal pull-ups: pressed = LOW
  pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUTTON2_PIN, INPUT_PULLUP);

  // XIAO nRF52840 ADC
  analogReadResolution(12);

  // Initialize BLE
  if (!BLE.begin()) {
    Serial.println("BLE initialization failed!");

    while (true) {
      delay(1000);
    }
  }

  BLE.setLocalName(DEVICE_NAME);
  BLE.setAdvertisedService(recordingService);

  recordingService.addCharacteristic(dataCharacteristic);
  BLE.addService(recordingService);

  dataCharacteristic.writeValue("READY");

  BLE.advertise();

  Serial.println("XIAO BLE advertising started");
  Serial.print("Device name: ");
  Serial.println(DEVICE_NAME);
  Serial.println("Waiting for Raspberry Pi...");
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
  // Keep the BLE stack running
  BLE.poll();

  // ----------------------------------------------------------
  // 1. BUTTON 1: START / STOP
  // ----------------------------------------------------------

  int reading = digitalRead(RECORD_BUTTON_PIN);

  if (reading != lastButtonReading) {
    lastDebounceTime = millis();
    lastButtonReading = reading;
  }

  if (millis() - lastDebounceTime >= DEBOUNCE_MS) {
    if (reading != stableButtonState) {
      stableButtonState = reading;

      // Button pressed = LOW
      if (stableButtonState == LOW) {
        if (!recording) {
          startRecording();
        } else {
          stopRecording();
        }
      }
    }
  }

  // ----------------------------------------------------------
  // 2. SAMPLE SENSOR AND BUTTON 2
  // ----------------------------------------------------------

  if (recording &&
      millis() - lastSampleTime >= SAMPLE_INTERVAL_MS) {

    lastSampleTime = millis();

    // Timestamp in milliseconds since startup
    unsigned long timestamp = millis();

    // Read ADC input
    int adcValue = analogRead(ADC_PIN);

    // LOW = pressed (1), HIGH = released (0)
    int button2State =
        (digitalRead(BUTTON2_PIN) == LOW) ? 1 : 0;

    // Packet format:
    // D,timestamp_ms,adc_value,button2_state
    //
    // Compact enough for a 20-byte BLE characteristic.
    char packet[21];

    snprintf(
        packet,
        sizeof(packet),
        "D,%lu,%d,%d\n",
        timestamp,
        adcValue,
        button2State
    );

    sendMessage(packet);

    // USB Serial debugging
    Serial.print(packet);
  }

  delay(1);
}