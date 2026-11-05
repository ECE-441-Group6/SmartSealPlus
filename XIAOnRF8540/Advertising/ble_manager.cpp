#include "ble_manager.h"

#include <bluefruit.h>
#include <Adafruit_nRFCrypto.h>
#include <nrf_cc310/include/crys_aesccm.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

#include "config.h"
#include "secrets.h"

namespace {
constexpr char DEVICE_NAME[] = "SmartSeal-XIAO";
constexpr uint16_t GATEWAY_MANUFACTURER_ID = 0x5353;
constexpr uint8_t PACKET_VERSION = 2;
constexpr size_t NONCE_LENGTH = 8;
constexpr size_t PLAINTEXT_LENGTH = 10;
constexpr size_t TAG_LENGTH = 8;
constexpr size_t ENCRYPTED_PACKET_LENGTH =
  1 + NONCE_LENGTH + PLAINTEXT_LENGTH + TAG_LENGTH;
static_assert(sizeof(SMARTSEAL_ENCRYPTION_KEY) == 16, "AES-128 key required");
static_assert(
  ENCRYPTED_PACKET_LENGTH + 4 <= 31,
  "Encrypted manufacturer data must fit in a BLE advertisement"
);

uint32_t advertisementSequence = 0;

bool generateNonce(uint8_t *nonce) {
  return nRFCrypto.Random.generate(nonce, NONCE_LENGTH);
}

bool encryptPacket(
  const uint8_t *plaintext,
  uint8_t *packet
) {
  packet[0] = PACKET_VERSION;
  if (!generateNonce(packet + 1)) {
    return false;
  }

  CRYS_AESCCM_Key_t key = {};
  memcpy(key, SMARTSEAL_ENCRYPTION_KEY, sizeof(SMARTSEAL_ENCRYPTION_KEY));
  CRYS_AESCCM_UserContext_t context = {};
  CRYS_AESCCM_Mac_Res_t tag = {};
  uint8_t plaintextBuffer[PLAINTEXT_LENGTH];
  memcpy(plaintextBuffer, plaintext, sizeof(plaintextBuffer));
  uint8_t tagLength = TAG_LENGTH;
  uint8_t authenticatedVersion = PACKET_VERSION;

  if (CRYS_AESCCM_Init(
        &context,
        SASI_AES_ENCRYPT,
        key,
        CRYS_AES_Key128BitSize,
        sizeof(authenticatedVersion),
        PLAINTEXT_LENGTH,
        packet + 1,
        NONCE_LENGTH,
        TAG_LENGTH
      ) != CRYS_OK) {
    return false;
  }
  if (CRYS_AESCCM_BlockAdata(
        &context,
        &authenticatedVersion,
        sizeof(authenticatedVersion)
      ) != CRYS_OK) {
    return false;
  }
  if (CRYS_AESCCM_Finish(
        &context,
        plaintextBuffer,
        PLAINTEXT_LENGTH,
        packet + 1 + NONCE_LENGTH,
        tag,
        &tagLength
      ) != CRYS_OK ||
      tagLength != TAG_LENGTH) {
    return false;
  }
  memcpy(
    packet + 1 + NONCE_LENGTH + PLAINTEXT_LENGTH,
    tag,
    TAG_LENGTH
  );
  return true;
}

void addManufacturerPacket(const uint8_t *packet, size_t packetLength) {
  uint8_t manufacturerData[2 + ENCRYPTED_PACKET_LENGTH];
  manufacturerData[0] =
    static_cast<uint8_t>(GATEWAY_MANUFACTURER_ID & 0xFF);
  manufacturerData[1] =
    static_cast<uint8_t>(GATEWAY_MANUFACTURER_ID >> 8);
  memcpy(manufacturerData + 2, packet, packetLength);
  Bluefruit.Advertising.addManufacturerData(
    manufacturerData,
    packetLength + 2
  );
}

void setEncryptedAdvertisement(const uint8_t *packet) {
  Bluefruit.Advertising.clearData();
  addManufacturerPacket(packet, ENCRYPTED_PACKET_LENGTH);
  Bluefruit.ScanResponse.clearData();
  Bluefruit.ScanResponse.addName();
}
}

bool initializeBle() {
  Bluefruit.begin();
  Bluefruit.setName(DEVICE_NAME);
  if (!nRFCrypto.begin()) {
    Serial.println("ERROR: nRF CryptoCell initialization failed.");
    return false;
  }

  const uint8_t initialPlaintext[PLAINTEXT_LENGTH] = {
    SMARTSEAL_SEAL_ID,
    0, 0, 0, 0,
    0, 0,
    0,
    0, 0
  };
  uint8_t initialPacket[ENCRYPTED_PACKET_LENGTH];
  if (!encryptPacket(initialPlaintext, initialPacket)) {
    Serial.println("ERROR: hardware RNG failed; encrypted BLE is disabled.");
    return false;
  }

  setEncryptedAdvertisement(initialPacket);
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);

  Serial.println("BLE manufacturer advertising started.");
  Serial.print("Device name: ");
  Serial.println(DEVICE_NAME);
  return true;
}

bool updateGatewayAdvertisement(
  float temperatureC,
  bool vibrationDetected
) {
  if (!isfinite(temperatureC) ||
      temperatureC < -3276.8f ||
      temperatureC > 3276.7f) {
    return false;
  }

  const int16_t temperatureTenths =
    static_cast<int16_t>(lroundf(temperatureC * 10.0f));
  const uint16_t vibrationValue = vibrationDetected ? 100 : 0;
  const uint32_t sequence = advertisementSequence + 1;
  const uint8_t plaintext[PLAINTEXT_LENGTH] = {
    SMARTSEAL_SEAL_ID,
    static_cast<uint8_t>(sequence & 0xFF),
    static_cast<uint8_t>((sequence >> 8) & 0xFF),
    static_cast<uint8_t>((sequence >> 16) & 0xFF),
    static_cast<uint8_t>((sequence >> 24) & 0xFF),
    static_cast<uint8_t>(temperatureTenths & 0xFF),
    static_cast<uint8_t>((temperatureTenths >> 8) & 0xFF),
    0,
    static_cast<uint8_t>(vibrationValue & 0xFF),
    static_cast<uint8_t>((vibrationValue >> 8) & 0xFF)
  };
  uint8_t packet[ENCRYPTED_PACKET_LENGTH];
  if (!encryptPacket(plaintext, packet)) {
    Serial.println("ERROR: hardware RNG failed; packet was not advertised.");
    return false;
  }
  advertisementSequence = sequence;

  Bluefruit.Advertising.stop();
  setEncryptedAdvertisement(packet);
  Bluefruit.Advertising.start(0);

  Serial.print("Advertisement updated: sequence=");
  Serial.print(sequence);
  Serial.print(", temperature C=");
  Serial.print(temperatureC, 1);
  Serial.print(", vibration=");
  Serial.println(vibrationDetected ? 1 : 0);
  return true;
}
