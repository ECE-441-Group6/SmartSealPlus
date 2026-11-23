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
// Sequence values are serialized little-endian so the gateway builds the same
// nonce bytes from the transmitted packet.
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

    // CryptoCell's AES-CCM operation produces ciphertext and a separate tag.
    // The key is copied from the local, untracked secrets.h configuration.
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
    float vibrationMagnitudeVolts,
    uint8_t movementCode,
    uint8_t *packet
) {

    // Reject invalid readings before consuming a sequence number; the sequence
    // is also the changing part of the CCM nonce.
    if (!isfinite(temperatureC) ||
        temperatureC < -3276.8f ||
        temperatureC > 3276.7f) {

        return false;
    }

    int16_t temperatureTenths =
        (int16_t)lroundf(temperatureC * 10.0f);

    if (!isfinite(vibrationMagnitudeVolts) ||
        vibrationMagnitudeVolts < 0.0f ||
        vibrationMagnitudeVolts > 65.535f) {
        return false;
    }

    // Encode the peak sensor deviation as whole millivolts in the BLE packet.
    const uint16_t vibrationMagnitude = static_cast<uint16_t>(
        lroundf(vibrationMagnitudeVolts * 1000.0f)
    );

    if (movementCode > MOVEMENT_SHAKE) {
        return false;
    }

    // Validate all caller-provided values before allocating a nonce sequence.
    // Invalid readings should not create gaps in the sequence stream.
    uint32_t sequence;
    if (!getNextSequence(sequence)) {
        return false;
    }

    // -------------------------------------------------
    // Build packet header and nonce
    // -------------------------------------------------

    packet[0] = MAGIC;
    packet[1] = PROTOCOL_VERSION;
    packet[2] = SEAL_ID;
    encodeUint32(packet + 3, sequence);

    uint8_t nonce[NONCE_LENGTH];
    memcpy(nonce, NONCE_PREFIX, 9);

    // Use exactly the same sequence bytes as the transmitted packet.
    memcpy(nonce + 9, packet + 3, 4);

    // -------------------------------------------------
    // Build plaintext sensor data
    // -------------------------------------------------

    // Plaintext layout: temperature x10 (signed LE), tamper flag,
    // vibration magnitude x100 (unsigned LE), movement code.
    uint8_t plaintext[PLAINTEXT_LENGTH];

    uint16_t temperatureRaw =
        (uint16_t)temperatureTenths;

    plaintext[0] = temperatureRaw & 0xFF;
    plaintext[1] = (temperatureRaw >> 8) & 0xFF;

    // Tamper is currently not connected to this sketch.
    plaintext[2] = 0;

    plaintext[3] = vibrationMagnitude & 0xFF;
    plaintext[4] = (vibrationMagnitude >> 8) & 0xFF;
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

    // The BLE manufacturer field is company ID (little-endian) followed by
    // the fixed-size encrypted packet defined above.
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

    // Use BLE advertising interval units (0.625 ms): range 20 to 152.5 ms.
    Bluefruit.Advertising.setInterval(32, 244);

    // Duration zero means advertise until stopEncryptedAdvertising() is called.
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
