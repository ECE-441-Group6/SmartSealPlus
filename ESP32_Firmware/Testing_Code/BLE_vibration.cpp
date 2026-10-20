#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// ============================================================
// PIN CONFIGURATION
// ============================================================

const int RECORD_BUTTON_PIN = 25;  // Button 1: start/stop
const int ADC_PIN           = 34;  // Analog sensor input
const int BUTTON2_PIN       = 32;  // Button 2: state logging

// ============================================================
// BLE CONFIGURATION
// ============================================================

#define DEVICE_NAME "ESP32_Recorder"

#define SERVICE_UUID \
  "12345678-1234-1234-1234-1234567890ab"

#define CHARACTERISTIC_UUID \
  "12345678-1234-1234-1234-1234567890ac"

BLECharacteristic *dataCharacteristic;

// ============================================================
// RECORDING SETTINGS
// ============================================================

// 10 ms interval = nominal 100 Hz sampling
const unsigned long SAMPLE_INTERVAL_MS = 10;

// Button debounce interval
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

void sendMessage(const String &message) {
  dataCharacteristic->setValue(message.c_str());
  dataCharacteristic->notify();
}

// ============================================================
// START RECORDING
// ============================================================

void startRecording() {
  if (recording) return;

  recording = true;
  lastSampleTime = millis();

  Serial.println("Recording started");

  // Tell Raspberry Pi to create a new CSV
  sendMessage("START\n");
}

// ============================================================
// STOP RECORDING
// ============================================================

void stopRecording() {
  if (!recording) return;

  recording = false;

  Serial.println("Recording stopped");

  // Tell Raspberry Pi to close and save the CSV
  sendMessage("STOP\n");
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);

  // Both buttons are wired between GPIO and GND
  pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUTTON2_PIN, INPUT_PULLUP);

  // ADC configuration: 12-bit values, 0 to 4095
  analogReadResolution(12);

  // ==========================================================
  // INITIALIZE BLE SERVER
  // ==========================================================

  BLEDevice::init(DEVICE_NAME);

  BLEServer *server = BLEDevice::createServer();

  BLEService *service =
      server->createService(SERVICE_UUID);

  dataCharacteristic = service->createCharacteristic(
      CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_READ |
      BLECharacteristic::PROPERTY_NOTIFY
  );

  dataCharacteristic->addDescriptor(new BLE2902());
  dataCharacteristic->setValue("READY");

  service->start();

  BLEAdvertising *advertising =
      BLEDevice::getAdvertising();

  advertising->addServiceUUID(SERVICE_UUID);
  advertising->setScanResponse(true);
  advertising->start();

  Serial.println("BLE advertising started");
  Serial.println("Device name: ESP32_Recorder");
  Serial.println("Waiting for Raspberry Pi...");
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {

  // ----------------------------------------------------------
  // 1. READ BUTTON 1 AND DEBOUNCE
  // ----------------------------------------------------------

  int reading = digitalRead(RECORD_BUTTON_PIN);

  if (reading != lastButtonReading) {
    lastDebounceTime = millis();
    lastButtonReading = reading;
  }

  if (millis() - lastDebounceTime >= DEBOUNCE_MS) {

    if (reading != stableButtonState) {
      stableButtonState = reading;

      // LOW means Button 1 is pressed
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
  // 2. RECORD ADC VALUE, TIMESTAMP, AND BUTTON 2 STATE
  // ----------------------------------------------------------

  if (recording &&
      millis() - lastSampleTime >= SAMPLE_INTERVAL_MS) {

    lastSampleTime = millis();

    // Timestamp in milliseconds since ESP32 boot
    unsigned long timestamp = millis();

    // Read raw ADC value from GPIO34
    int adcValue = analogRead(ADC_PIN);

    // Button 2: LOW = pressed (1), HIGH = released (0)
    int button2State =
        (digitalRead(BUTTON2_PIN) == LOW) ? 1 : 0;

    // Packet format:
    // D,timestamp_ms,adc_value,button2_state
    String packet = "D," +
                    String(timestamp) + "," +
                    String(adcValue) + "," +
                    String(button2State) + "\n";

    // Send sample through BLE
    sendMessage(packet);

    // Optional USB serial debugging
    Serial.print(packet);
  }

  delay(1);
}