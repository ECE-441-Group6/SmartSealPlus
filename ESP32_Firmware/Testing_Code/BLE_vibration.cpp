

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
BLEAdvertising *pAdvertising = nullptr;

volatile bool deviceConnected = false;

// ============================================================
// RECORDING SETTINGS
// ============================================================

// Nominal sampling interval: 10 ms = 100 Hz
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

    Serial.println();
    Serial.println("================================");
    Serial.println("BLE CLIENT CONNECTED");
    Serial.println("Raspberry Pi connection established");
    Serial.println("================================");
  }

  void onDisconnect(BLEServer *server) override {
    deviceConnected = false;

    Serial.println();
    Serial.println("BLE CLIENT DISCONNECTED");

    if (recording) {
      recording = false;
      Serial.println("Recording stopped due to disconnect.");
    }

    Serial.println("Restarting BLE advertising...");

    // Restart advertising so the Pi can reconnect.
    BLEDevice::startAdvertising();

    Serial.println("BLE advertising restarted.");
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

  Serial.println("Recording started.");

  // Tell Raspberry Pi to create a new CSV.
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

  Serial.println("Recording stopped.");

  // Tell Raspberry Pi to save and close the CSV.
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
  Serial.println("Starting...");
  Serial.println("================================");

  // Buttons are wired between GPIO and GND.
  pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUTTON2_PIN, INPUT_PULLUP);

  // ADC resolution: 12-bit (0-4095).
  analogReadResolution(12);

  // ----------------------------------------------------------
  // INITIALIZE BLE
  // ----------------------------------------------------------

  Serial.println("Initializing BLE...");

  BLEDevice::init(DEVICE_NAME);

  pServer = BLEDevice::createServer();

  pServer->setCallbacks(new RecorderServerCallbacks());

  BLEService *service =
      pServer->createService(SERVICE_UUID);

  dataCharacteristic = service->createCharacteristic(
      CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_READ |
      BLECharacteristic::PROPERTY_NOTIFY
  );

  dataCharacteristic->addDescriptor(new BLE2902());
  dataCharacteristic->setValue("READY");

  service->start();

  pAdvertising = BLEDevice::getAdvertising();

  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);

  BLEDevice::startAdvertising();

  Serial.println("BLE advertising started.");
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
  // 2. SAMPLE ADC AND BUTTON 2
  // ----------------------------------------------------------

  if (recording &&
      millis() - lastSampleTime >= SAMPLE_INTERVAL_MS) {

    lastSampleTime = millis();

    // Timestamp since ESP32 boot.
    unsigned long timestamp = millis();

    // Raw ADC reading from GPIO34.
    int adcValue = analogRead(ADC_PIN);

    // Button 2: LOW = pressed (1), HIGH = released (0).
    int button2State =
        (digitalRead(BUTTON2_PIN) == LOW) ? 1 : 0;

    // Data format expected by the Raspberry Pi:
    // D,timestamp_ms,adc_value,button2_state
    String packet = "D," +
                    String(timestamp) + "," +
                    String(adcValue) + "," +
                    String(button2State) + "\n";

    // Send the notification if connected.
    sendMessage(packet);

    // Print sample for serial debugging.
    Serial.print(packet);
  }

  // Yield CPU time to other tasks.
  delay(1);
}
