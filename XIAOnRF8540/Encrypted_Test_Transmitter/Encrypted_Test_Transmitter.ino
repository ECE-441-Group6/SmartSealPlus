#include <Arduino.h>
#include <Adafruit_TinyUSB.h>
#include <Adafruit_nRFCrypto.h>
#include <bluefruit.h>
#include <stdint.h>
#include <string.h>
#include <nrf_cc310/include/crys_aesccm.h>

#include "secrets.h"
#include "sequence_manager.h"

namespace {
constexpr uint16_t MANUFACTURER_ID = 0x5353;
constexpr uint8_t MAGIC = 0xA5;
constexpr uint8_t PROTOCOL_VERSION = 3;
constexpr uint8_t NONCE_LENGTH = 13;
constexpr uint8_t TAG_LENGTH = 8;
constexpr uint8_t HEADER_LENGTH = 7;
constexpr uint8_t PLAINTEXT_LENGTH = 6;
constexpr uint8_t PACKET_LENGTH = 21;
constexpr uint32_t ADVERTISEMENT_INTERVAL_MS = 5000;

uint32_t lastAdvertisement = 0;
uint8_t scenario = 0;

bool encryptPlaintext(const uint8_t *plaintext, const uint8_t *aad,
                      const uint8_t *nonce, uint8_t *ciphertext,
                      uint8_t *tag) {
  CRYS_AESCCM_Key_t ccmKey = {0};
  memcpy(ccmKey, AES_KEY, sizeof(AES_KEY));
  CRYS_AESCCM_Mac_Res_t mac = {0};
  const CRYSError_t result = CRYS_AESCCM(
      SASI_AES_ENCRYPT, ccmKey, CRYS_AES_Key128BitSize,
      const_cast<uint8_t *>(nonce), NONCE_LENGTH,
      const_cast<uint8_t *>(aad), HEADER_LENGTH,
      const_cast<uint8_t *>(plaintext), PLAINTEXT_LENGTH,
      ciphertext, TAG_LENGTH, mac);
  if (result != CRYS_OK) {
    Serial.print("AES-CCM encryption error: 0x");
    Serial.println(static_cast<uint32_t>(result), HEX);
    return false;
  }
  memcpy(tag, mac, TAG_LENGTH);
  return true;
}

bool makeTestPacket(uint8_t *packet) {
  uint32_t sequence = 0;
  if (!getNextSequence(sequence)) {
    Serial.println("Could not allocate a safe packet sequence.");
    return false;
  }

  // Synthetic values let the gateway's event handling be exercised without
  // sensors. Temperature is tenths of a degree C; vibration is hundredths
  // of a volt. Movement codes match the production firmware.
  static const int16_t temperatures[] = {40, 90, 200, -10};
  static const uint16_t vibrationValues[] = {0, 100, 0, 250};
  static const uint8_t tamperValues[] = {0, 1, 0, 1};
  static const uint8_t movements[] = {0, 0, 1, 4};
  const uint8_t sample = scenario++ % 4;

  packet[0] = MAGIC;
  packet[1] = PROTOCOL_VERSION;
  packet[2] = SEAL_ID;
  packet[3] = sequence & 0xFF;
  packet[4] = (sequence >> 8) & 0xFF;
  packet[5] = (sequence >> 16) & 0xFF;
  packet[6] = (sequence >> 24) & 0xFF;

  uint8_t nonce[NONCE_LENGTH];
  memcpy(nonce, NONCE_PREFIX, 9);
  memcpy(nonce + 9, packet + 3, 4);

  const uint16_t temp = static_cast<uint16_t>(temperatures[sample]);
  const uint8_t plaintext[PLAINTEXT_LENGTH] = {
      static_cast<uint8_t>(temp & 0xFF),
      static_cast<uint8_t>(temp >> 8),
      tamperValues[sample],
      static_cast<uint8_t>(vibrationValues[sample] & 0xFF),
      static_cast<uint8_t>(vibrationValues[sample] >> 8),
      movements[sample]};

  uint8_t ciphertext[PLAINTEXT_LENGTH];
  uint8_t tag[TAG_LENGTH];
  if (!encryptPlaintext(plaintext, packet, nonce, ciphertext, tag)) {
    return false;
  }
  memcpy(packet + 7, ciphertext, sizeof(ciphertext));
  memcpy(packet + 13, tag, sizeof(tag));

  Serial.print("Test packet: seal=");
  Serial.print(SEAL_ID);
  Serial.print(" sequence=");
  Serial.print(sequence);
  Serial.print(" scenario=");
  Serial.println(sample);
  return true;
}

void advertise(const uint8_t *packet) {
  uint8_t manufacturerData[2 + PACKET_LENGTH];
  manufacturerData[0] = MANUFACTURER_ID & 0xFF;
  manufacturerData[1] = MANUFACTURER_ID >> 8;
  memcpy(manufacturerData + 2, packet, PACKET_LENGTH);

  Bluefruit.Advertising.stop();
  Bluefruit.Advertising.clearData();
  Bluefruit.Advertising.addFlags(
      BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addManufacturerData(
      manufacturerData, sizeof(manufacturerData));
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.start(0);
}

void sendSample() {
  uint8_t packet[PACKET_LENGTH];
  if (makeTestPacket(packet)) {
    advertise(packet);
    lastAdvertisement = millis();
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("SmartSeal sensorless BLE test transmitter");

  while (!nRFCrypto.begin()) {
    Serial.println("CryptoCell initialization failed; retrying.");
    delay(1000);
  }

  // This test board has no external button. Sequence initialization is
  // enabled only through an explicit build-time provisioning setting.
  if (!initializeSequenceCounter(ALLOW_SEQUENCE_PROVISIONING)) {
    Serial.println("Sequence storage initialization failed; advertising stopped.");
    while (true) delay(1000);
  }

  Bluefruit.begin();
  Bluefruit.setName("SmartSeal-Test");
  Serial.println("Advertising starts immediately and updates every 5 seconds.");
  sendSample();
}

void loop() {
  const uint32_t now = millis();
  if (now - lastAdvertisement >= ADVERTISEMENT_INTERVAL_MS) {
    sendSample();
  }
  delay(10);
}
