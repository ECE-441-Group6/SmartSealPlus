#include "ble_manager.h"

#include <Adafruit_nRFCrypto.h>
#include <bluefruit.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
#include <nrf_cc310/include/crys_aesccm.h>

#include "config.h"
#include "accelerometer.h"
#include "sequence_manager.h"

namespace {
void encodeUint32(uint8_t *destination, uint32_t value) {
  destination[0] = value & 0xFF;
  destination[1] = (value >> 8) & 0xFF;
  destination[2] = (value >> 16) & 0xFF;
  destination[3] = (value >> 24) & 0xFF;
}
}

bool encryptSensorData(
    const uint8_t *plaintext,
    const uint8_t *aad,
    const uint8_t *nonce,
    uint8_t *ciphertext,
    uint8_t *tag
) {

    CRYS_AESCCM_Key_t ccmKey = {0};

    // Copy the 128-bit key into CryptoCell's key buffer.
    memcpy(ccmKey, AES_KEY, sizeof(AES_KEY));

    CRYS_AESCCM_Mac_Res_t mac = {0};

    CRYSError_t result = CRYS_AESCCM(
        SASI_AES_ENCRYPT,
        ccmKey,
        CRYS_AES_Key128BitSize,
        (uint8_t *)nonce,
        NONCE_LENGTH,
        (uint8_t *)aad,
        HEADER_LENGTH,
        (uint8_t *)plaintext,
        PLAINTEXT_LENGTH,
        ciphertext,
        TAG_LENGTH,
        mac
    );

    if (result != CRYS_OK) {

        Serial.print("AES-CCM encryption error: ");
        Serial.println((uint32_t)result, HEX);

        return false;
    }

    memcpy(tag, mac, TAG_LENGTH);

    return true;
}

// =====================================================
// 8. BUILD ENCRYPTED BLE PACKET
// =====================================================

bool createEncryptedPacket(
    float temperatureC,
    bool vibrationDetected,
    uint8_t movementCode,
    uint8_t *packet
) {

    if (!isfinite(temperatureC) ||
        temperatureC < -3276.8f ||
        temperatureC > 3276.7f) {

        return false;
    }

    uint32_t sequence;

    if (!getNextSequence(sequence)) {
        return false;
    }

    // -------------------------------------------------
    // Build packet header
    // -------------------------------------------------

    packet[0] = MAGIC;
    packet[1] = PROTOCOL_VERSION;
    packet[2] = SEAL_ID;

    encodeUint32(packet + 3, sequence);

    // -------------------------------------------------
    // Build 13-byte nonce
    // -------------------------------------------------

    uint8_t nonce[NONCE_LENGTH];

    memcpy(nonce, NONCE_PREFIX, 9);

    // Use exactly the same sequence bytes as the
    // transmitted packet. Python uses payload[3:7].

    memcpy(nonce + 9, packet + 3, 4);

    // -------------------------------------------------
    // Build plaintext sensor data
    // -------------------------------------------------

    int16_t temperatureTenths =
        (int16_t)lroundf(temperatureC * 10.0f);

    uint16_t vibrationValue =
        vibrationDetected ? 100 : 0;

    if (movementCode > MOVEMENT_SHAKE) {
        return false;
    }

    uint8_t plaintext[PLAINTEXT_LENGTH];

    uint16_t temperatureRaw =
        (uint16_t)temperatureTenths;

    plaintext[0] = temperatureRaw & 0xFF;
    plaintext[1] = (temperatureRaw >> 8) & 0xFF;

    // Tamper is currently not connected to this sketch.
    plaintext[2] = 0;

    plaintext[3] = vibrationValue & 0xFF;
    plaintext[4] = (vibrationValue >> 8) & 0xFF;
    plaintext[5] = movementCode;

    // -------------------------------------------------
    // Encrypt and authenticate
    // -------------------------------------------------

    uint8_t ciphertext[PLAINTEXT_LENGTH];

    uint8_t tag[TAG_LENGTH];

    // Header + sequence are authenticated as AAD.
    // They remain visible but cannot be modified
    // without authentication failure.

    if (!encryptSensorData(
            plaintext,
            packet,
            nonce,
            ciphertext,
            tag)) {

        return false;
    }

    // -------------------------------------------------
    // Assemble final packet
    // -------------------------------------------------

    memcpy(packet + 7, ciphertext, PLAINTEXT_LENGTH);

    memcpy(packet + 13, tag, TAG_LENGTH);

    return true;
}

// =====================================================
// 9. BLE ADVERTISING
// =====================================================

void startEncryptedAdvertising(const uint8_t *packet) {

    uint8_t manufacturerData[23];

    // Company ID, little-endian.
    manufacturerData[0] =
        MANUFACTURER_ID & 0xFF;

    manufacturerData[1] =
        MANUFACTURER_ID >> 8;

    memcpy(
        manufacturerData + 2,
        packet,
        PACKET_LENGTH
    );

    Bluefruit.Advertising.stop();

    Bluefruit.Advertising.clearData();

    Bluefruit.Advertising.addFlags(
        BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
    );

    Bluefruit.Advertising.addTxPower();

    Bluefruit.Advertising.addManufacturerData(
        manufacturerData,
        sizeof(manufacturerData)
    );

    Bluefruit.ScanResponse.clearData();

    Bluefruit.ScanResponse.addName();

    Bluefruit.Advertising.setInterval(32, 244);

    Bluefruit.Advertising.start(0);
}

void stopEncryptedAdvertising() {
    Bluefruit.Advertising.stop();
}

void initializeBle() {
  Bluefruit.begin();
  Bluefruit.setName("SmartSeal-XIAO");
  Serial.println("BLE initialized.");
}
