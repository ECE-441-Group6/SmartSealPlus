
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// ============================================================
// PIN CONFIGURATION
// ============================================================

const int RECORD_BUTTON_PIN = 25;  // Button 1: start/stop
const int ADC_PIN           = 34;  // Analog vibration sensor
const int BUTTON2_PIN       = 32;  // Button 2: state logging

// ============================================================
// BLE CONFIGURATION
// ============================================================

#define DEVICE_NAME "ESP32_Recorder"

#define SERVICE_UUID \
  "12345678-1234-1234-1234-1234567890ab"

#define CHARACTERISTIC_UUID \
  "12345678-1234-1234-1234-1234567890ac"

BLEServer *pServer = nullptr;
BLECharacteristic *dataCharacteristic = nullptr;

// Connection state
bool deviceConnected = false;

// ============================================================
// RECORDING SETTINGS
// ============================================================

// Nominal sampling interval: 10 ms (100 Hz)
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
// BLE SERVER CALLBACKS
// ============================================================

class RecorderServerCallbacks : public BLEServerCallbacks {

  void onConnect(BLEServer *server) override {
    deviceConnected = true;

    Serial.println("================================");
    Serial.println("Raspberry Pi connected!");
    Serial.println("BLE connection established");
    Serial.println("================================");
  }

  void onDisconnect(BLEServer *server) override {
    deviceConnected = false;

    Serial.println("Raspberry Pi disconnected");

    // If a recording was active, stop it safely.
    // The Pi cannot receive STOP while disconnected.
    if (recording) {
      recording = false;
      Serial.println("Recording stopped: BLE disconnected");
    }

    // Restart advertising so the Raspberry Pi can reconnect.
    BLEDevice::startAdvertising();

    Serial.println("BLE advertising restarted");
    Serial.println("Waiting for Raspberry Pi...");
  }
};

// ============================================================
// SEND BLE MESSAGE
// ============================================================

void sendMessage(const String &message) {
  if (!deviceConnected || dataCharacteristic == nullptr) {
    return;
  }

  dataCharacteristic->setValue(message.c_str());
  dataCharacteristic->notify();
}

// ============================================================
// START RECORDING
// ============================================================

void startRecording() {
  if (recording) {
    return;
  }

  recording = true;
  lastSampleTime = millis();

  Serial.println("Recording started");

  // Tell Raspberry Pi to create a new CSV file.
  sendMessage("START\n");
}

// ============================================================
// STOP RECORDING
// ============================================================

void stopRecording() {
  if (!recording) {
    return;
  }

  recording = false;

  Serial.println("Recording stopped");

  // Tell Raspberry Pi to close and save the CSV file.
  sendMessage("STOP\n");
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("================================");
  Serial.println("SmartSealPlus ESP32 Recorder");
  Serial.println("Initializing...");
  Serial.println("================================");

  // Buttons are wired between GPIO and GND.
  pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUTTON2_PIN, INPUT_PULLUP);

  // ADC configuration: 12-bit readings (0-4095).
  analogReadResolution(12);

  // ==========================================================
  // INITIALIZE BLE SERVER
  // ==========================================================

  Serial.println("Initializing BLE...");

  BLEDevice::init(DEVICE_NAME);

  pServer = BLEDevice::createServer();

  // Register connection/disconnection callbacks.
  pServer->setCallbacks(new RecorderServerCallbacks());

  BLEService *service =
      pServer->createService(SERVICE_UUID);

  dataCharacteristic = service->createCharacteristic(
      CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_READ |
      BLECharacteristic::PROPERTY_NOTIFY
  );

  // Enable notification support for BLE clients.
  dataCharacteristic->addDescriptor(new BLE2902());
  dataCharacteristic->setValue("READY");

  // Start the BLE service.
  service->start();

  // Configure and start advertising.
  BLEAdvertising *advertising =
      BLEDevice::getAdvertising();

  advertising->addServiceUUID(SERVICE_UUID);
  advertising->setScanResponse(true);

  BLEDevice::startAdvertising();

  Serial.println("BLE advertising started");
  Serial.print("Device name: ");
  Serial.println(DEVICE_NAME);

  Serial.print("Service UUID: ");
  Serial.println(SERVICE_UUID);

  Serial.print("Characteristic UUID: ");
  Serial.println(CHARACTERISTIC_UUID);

  Serial.println("Waiting for Raspberry Pi...");
  Serial.println("Press Button 1 to start/stop recording.");
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

      // LOW means Button 1 is pressed.
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

    // Timestamp in milliseconds since ESP32 boot.
    unsigned long timestamp = millis();

    // Read raw ADC value from GPIO34.
    int adcValue = analogRead(ADC_PIN);

    // Button 2: LOW = pressed (1), HIGH = released (0).
    int button2State =
        (digitalRead(BUTTON2_PIN) == LOW) ? 1 : 0;

    // Packet format:
    // D,timestamp_ms,adc_value,button2_state
    String packet = "D," +
                    String(timestamp) + "," +
                    String(adcValue) + "," +
                    String(button2State) + "\n";

    // Send the sample to the Raspberry Pi.
    sendMessage(packet);

    // Also print samples to USB serial for debugging.
    Serial.print(packet);
  }

  // Short delay yields CPU time to other tasks.
  delay(1);
}