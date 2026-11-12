#include <Arduino.h>
#include <Adafruit_nRFCrypto.h>
#include <bluefruit.h>
#include <stdint.h>

#define SMARTSEAL_SECRETS_HEADER "../SmartSeal_Encrypted_Test/secrets_test.h"

#include "../SmartSeal_Encrypted/config.h"
#include "../SmartSeal_Encrypted/ble_manager.h"
#include "../SmartSeal_Encrypted/sequence_manager.h"

namespace {
uint32_t lastAdvertisement = 0;
uint32_t sampleNumber = 0;

uint32_t packetSequence(const uint8_t *packet) {
    return
        (uint32_t)packet[3]
        | ((uint32_t)packet[4] << 8)
        | ((uint32_t)packet[5] << 16)
        | ((uint32_t)packet[6] << 24);
}

void publishTestPacket() {
    const uint32_t sample = sampleNumber++;
    const float temperature = 18.0f + (sample % 100) / 10.0f;
    const bool vibrationDetected = sample % 4 == 0;
    const uint8_t movementCode = sample % 5;

    uint8_t packet[PACKET_LENGTH];
    if (!createEncryptedPacket(
            temperature,
            vibrationDetected,
            movementCode,
            packet)) {
        Serial.println("Could not create sensorless test packet.");
        return;
    }

    startEncryptedAdvertising(packet);
    Serial.print("Advertising simulated seal ");
    Serial.print(SEAL_ID);
    Serial.print(", sequence ");
    Serial.print(packetSequence(packet));
    Serial.print(", temperature ");
    Serial.print(temperature, 1);
    Serial.print(" C, vibration ");
    Serial.print(vibrationDetected ? 1 : 0);
    Serial.print(", movement type ");
    Serial.println(movementCode);
}
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("SmartSeal+ sensorless multi-seal test transmitter");

    while (!nRFCrypto.begin()) {
        Serial.println("CryptoCell initialization failed; retrying.");
        delay(1000);
    }

    if (!initializeSequenceCounter()) {
        Serial.println("Could not initialize persistent sequence storage.");
        while (true) {
            delay(1000);
        }
    }

    initializeBle();
    Bluefruit.setName("SmartSeal-Test");
    publishTestPacket();
    lastAdvertisement = millis();
}

void loop() {
    const uint32_t now = millis();
    if (now - lastAdvertisement >= ADVERTISEMENT_INTERVAL_MS) {
        lastAdvertisement = now;
        publishTestPacket();
    }
    delay(10);
}

#include "../SmartSeal_Encrypted/ble_manager.cpp"
#include "../SmartSeal_Encrypted/sequence_manager.cpp"
