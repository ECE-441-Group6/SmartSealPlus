#include <Arduino.h>
#include <Adafruit_TinyUSB.h>
#include <Adafruit_nRFCrypto.h>
#include <math.h>
#include <stdint.h>
#include "ble_manager.h"
#include "config.h"
#include "accelerometer.h"
#include "sequence_manager.h"
#include "sensor_manager.h"

void publishSensorData();

namespace {
bool recording = false;
int lastButtonReading = HIGH;
int stableButtonState = HIGH;
uint32_t lastDebounceTime = 0;
uint32_t lastAdvertisement = 0;

void startRecording() {
    recording = true;
    calibrateVibrationSensor();
    resetMovementDetection();
    publishSensorData();
    lastAdvertisement = millis();
    Serial.println("Recording started; keep the seal still for calibration.");
}

void stopRecording() {
    recording = false;
    stopEncryptedAdvertising();
    Serial.println("Recording stopped.");
}

void updateRecordButton(uint32_t now) {
    const int reading = digitalRead(RECORD_BUTTON_PIN);
    if (reading != lastButtonReading) {
        lastButtonReading = reading;
        lastDebounceTime = now;
    }

    if (now - lastDebounceTime < BUTTON_DEBOUNCE_MS ||
        reading == stableButtonState) {
        return;
    }

    stableButtonState = reading;
    if (stableButtonState == LOW) {
        if (recording) {
            stopRecording();
        } else {
            startRecording();
        }
    }
}
}

void publishSensorData() {

    float temperature = readTemperatureC();

    const VibrationReading vibration = detectVibration();
    const uint8_t movementCode = getMovementCode();

    if (!isfinite(temperature)) {

        Serial.println("Invalid temperature reading.");
        return;
    }

    uint8_t encryptedPacket[PACKET_LENGTH];

    if (!createEncryptedPacket(
            temperature,
            vibration.detected,
            movementCode,
            encryptedPacket)) {

        Serial.println("Could not create encrypted packet.");
        return;
    }

    startEncryptedAdvertising(encryptedPacket);
    clearMovementCode();

    Serial.println();
    Serial.println("Encrypted BLE advertisement updated.");

    Serial.print("Temperature: ");
    Serial.println(temperature, 1);

    Serial.print("Vibration: ");
    Serial.println(vibration.detected ? 1 : 0);
    Serial.print("Movement type: ");
    Serial.println(movementCode);

    if (vibration.detected) {
        Serial.print("Vibration event detected. ADC: ");
        Serial.print(vibration.adcValue);
        Serial.print(", voltage: ");
        Serial.print(vibration.voltage, 3);
        Serial.print(" V, baseline: ");
        Serial.print(vibration.baseline, 1);
        Serial.print(", deviation: ");
        Serial.print(vibration.deviation, 1);
        Serial.print(" ADC (");
        Serial.print(
            vibration.deviation * ADC_REFERENCE_VOLTAGE / ADC_MAX,
            3
        );
        Serial.println(" V)");
    }

    Serial.print("Encrypted packet: ");

    for (uint8_t i = 0; i < PACKET_LENGTH; i++) {

        if (encryptedPacket[i] < 0x10) {
            Serial.print("0");
        }

        Serial.print(encryptedPacket[i], HEX);
        Serial.print(" ");
    }

    Serial.println();
}

void setup() {
    // Initialize serial communication.
    Serial.begin(115200);
    delay(1000);
    Serial.println();
    Serial.println("==============================");
    Serial.println(" SmartSeal+ Secure BLE");
    Serial.println("==============================");

    //PIN SETUP
    analogReadResolution(12); // Set ADC resolution to 12 bits (0-4095)
    pinMode(TEMP_PIN, INPUT);
    pinMode(VIBRATION_PIN, INPUT);
    pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP); //pin reads HIGH when not pressed, LOW when pressed
    

    //Initialize the accelerometer
    while (!accelerometerBegin()) {
        Serial.println("ERROR: Accelerometer initialization failed...Retrying");
        delay(1000);
    }

    // Initialize Nordic CryptoCell.
    while (!nRFCrypto.begin()) {
        Serial.println("ERROR: CryptoCell initialization failed...Retrying");    // Loop until the cryptoCell is initialized successfully.
        delay(1000);
    }
    Serial.println("CryptoCell initialized.");


    // Initialize persistent sequence storage.
    if (!initializeSequenceCounter()) {
        Serial.println("ERROR: Secure sequence initialization failed.");
        while (true) {
            delay(1000);
        }
    }

    initializeBle();
    Serial.println("SmartSeal secure advertiser ready.");
    Serial.println("Press button to start or stop recording.");
}


// =====================================================
// 12. MAIN LOOP
// =====================================================

void loop() {
    const uint32_t now = millis();
    updateRecordButton(now);

    if (recording) {
        updateVibrationSensor();
        detectMovement();
    }

    if (recording &&
        now - lastAdvertisement >=
        ADVERTISEMENT_INTERVAL_MS) {

        lastAdvertisement = now;

        publishSensorData();
    }

    delay(10); //100hz
}
