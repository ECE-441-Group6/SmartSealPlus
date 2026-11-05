#include "ble_manager.h"

#include <bluefruit.h>
#include <Adafruit_nRFCrypto.h>
#include <math.h>
#include <nrf.h>
#include <nrf_cc310/include/crys_aesccm.h>
#include <stdint.h>
#include <string.h>

#include "config.h"

namespace {
constexpr char DEVICE_NAME[] = "Xiao_Recorder";
constexpr uint16_t GATEWAY_MANUFACTURER_ID = 0x5353;
constexpr uint8_t PACKET_VERSION = 2;
constexpr uint8_t SEAL_ID = 1;
constexpr size_t NONCE_LENGTH = 7;
constexpr size_t PLAINTEXT_LENGTH = 10;
constexpr size_t TAG_LENGTH = 6;
constexpr size_t ENCRYPTED_PACKET_LENGTH =
  1 + NONCE_LENGTH + PLAINTEXT_LENGTH + TAG_LENGTH;
static_assert(sizeof(SMARTSEAL_ENCRYPTION_KEY) == 16,
              "SMARTSEAL_ENCRYPTION_KEY must be exactly 16 bytes");

uint32_t advertisementSequence = 0;

uint8_t randomByte() {
  NRF_RNG->EVENTS_VALRDY = 0;
  NRF_RNG->TASKS_START = 1;
  while (NRF_RNG->EVENTS_VALRDY == 0) {
  }
  const uint8_t value = NRF_RNG->VALUE;
  NRF_RNG->TASKS_STOP = 1;
  return value;
}

bool addManufacturerPacket(const uint8_t *packet, size_t packetLength) {
  if (!packet || packetLength != ENCRYPTED_PACKET_LENGTH) {
    return false;
  }
  uint8_t manufacturerData[2 + ENCRYPTED_PACKET_LENGTH];
  manufacturerData[0] =
    static_cast<uint8_t>(GATEWAY_MANUFACTURER_ID & 0xFF);
  manufacturerData[1] =
    static_cast<uint8_t>(GATEWAY_MANUFACTURER_ID >> 8);
  memcpy(manufacturerData + 2, packet, packetLength);
  return Bluefruit.Advertising.addManufacturerData(
    manufacturerData,
    packetLength + 2
  );
}

bool encryptPacket(
  float temperatureC,
  bool vibrationDetected,
  uint32_t sequence,
  uint8_t *encryptedPacket
) {
  const int16_t temperatureTenths =
    static_cast<int16_t>(lroundf(temperatureC * 10.0f));
  uint8_t plaintext[PLAINTEXT_LENGTH] = {
    SEAL_ID,
    static_cast<uint8_t>(sequence & 0xFF),
    static_cast<uint8_t>((sequence >> 8) & 0xFF),
    static_cast<uint8_t>((sequence >> 16) & 0xFF),
    static_cast<uint8_t>((sequence >> 24) & 0xFF),
    static_cast<uint8_t>(temperatureTenths & 0xFF),
    static_cast<uint8_t>((temperatureTenths >> 8) & 0xFF),
    0,
    static_cast<uint8_t>(vibrationDetected ? 100 : 0),
    0
  };
  uint8_t nonce[NONCE_LENGTH];
  for (size_t index = 0; index < sizeof(nonce); ++index) {
    nonce[index] = randomByte();
  }

  encryptedPacket[0] = PACKET_VERSION;
  memcpy(encryptedPacket + 1, nonce, sizeof(nonce));

  CRYS_AESCCM_Key_t key;
  memcpy(key, SMARTSEAL_ENCRYPTION_KEY, sizeof(key));
  uint8_t tag[CRYS_AESCCM_MAC_MAX_SIZE_BYTES] = {};
  const CRYSError_t result = CRYS_AESCCM(
    SASI_AES_ENCRYPT,
    key,
    CRYS_AES_Key128BitSize,
    nonce,
    sizeof(nonce),
    encryptedPacket,
    1,
    plaintext,
    sizeof(plaintext),
    encryptedPacket + 1 + NONCE_LENGTH,
    TAG_LENGTH,
    tag
  );
  if (result != CRYS_OK) {
    return false;
  }
  memcpy(
    encryptedPacket + 1 + NONCE_LENGTH + sizeof(plaintext),
    tag,
    TAG_LENGTH
  );
  return true;
}
}

bool initializeBle() {
  if (!nRFCrypto.begin()) {
    Serial.println("ERROR: BLE encryption library initialization failed.");
    return false;
  }
  Bluefruit.begin();
  Bluefruit.setName(DEVICE_NAME);

  Bluefruit.Advertising.setType(
    BLE_GAP_ADV_TYPE_NONCONNECTABLE_SCANNABLE_UNDIRECTED
  );
  if (!Bluefruit.Advertising.addFlags(
        BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
      ) ||
      !Bluefruit.ScanResponse.addName()) {
    Serial.println("ERROR: Could not configure BLE advertisement data.");
    return false;
  }
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  if (!Bluefruit.Advertising.start(0)) {
    Serial.println("ERROR: Could not start BLE advertising.");
    return false;
  }

  Serial.println("Non-connectable BLE advertising started.");
  Serial.print("Device name: ");
  Serial.println(DEVICE_NAME);
  Serial.println("Press D6 to start encrypted sensor broadcasts.");
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

  const uint32_t sequence = ++advertisementSequence;
  uint8_t packet[ENCRYPTED_PACKET_LENGTH];
  if (!encryptPacket(
        temperatureC,
        vibrationDetected,
        sequence,
        packet
      )) {
    Serial.println("BLE encryption failed; advertisement not updated.");
    return false;
  }

  if (Bluefruit.Advertising.isRunning() &&
      !Bluefruit.Advertising.stop()) {
    Serial.println("ERROR: Could not pause BLE advertising for update.");
    return false;
  }
  Bluefruit.Advertising.clearData();
  if (!Bluefruit.Advertising.addFlags(
        BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
      ) ||
      !addManufacturerPacket(packet, sizeof(packet))) {
    Serial.println("ERROR: Could not build encrypted BLE advertisement.");
    return false;
  }
  if (!Bluefruit.Advertising.start(0)) {
    Serial.println("ERROR: Could not resume BLE advertising.");
    return false;
  }

  Serial.print("Advertisement updated: sequence=");
  Serial.print(sequence);
  Serial.print(", temperature C=");
  Serial.print(temperatureC, 1);
  Serial.print(", vibration=");
  Serial.println(vibrationDetected ? 1 : 0);
  return true;
}
