#include "ble_manager.h"
#include "hmac_auth.h"
#include "device_secrets.h"

#include <bluefruit.h>
#include <math.h>
#include <stdio.h>

namespace {
BLEService sensorService(
  "12345678-1234-1234-1234-1234567890ab"
);
BLECharacteristic sensorCharacteristic(
  "12345678-1234-1234-1234-1234567890ac"
);
BLEService communicationService(
  "12345678-1234-1234-1234-1234567890ad"
);
BLECharacteristic heartbeatCharacteristic(
  "12345678-1234-1234-1234-1234567890ae"
);
BLECharacteristic acknowledgmentCharacteristic(
  "12345678-1234-1234-1234-1234567890af"
);

constexpr char DEVICE_NAME[] = "SmartSeal-XIAO";
constexpr unsigned long HEARTBEAT_INTERVAL_MS = 2000;

unsigned long lastHeartbeatMs = 0;
uint32_t heartbeatCounter = 0;
volatile uint32_t lastAcknowledgedSequence = 0;
volatile bool acknowledgmentReceived = false;

void connectCallback(uint16_t connectionHandle) {
  (void)connectionHandle;
  lastHeartbeatMs = millis();
  Serial.println("BLE: Raspberry Pi connected.");
}

void disconnectCallback(uint16_t connectionHandle, uint8_t reason) {
  (void)connectionHandle;
  Serial.print("BLE: Disconnected. Reason: ");
  Serial.println(reason);
}

void acknowledgmentWriteCallback(
  uint16_t connectionHandle,
  BLECharacteristic *characteristic,
  uint8_t *data,
  uint16_t length
) {
  (void)connectionHandle;
  (void)characteristic;

  if (length != 4) {
    Serial.println("BLE: Invalid acknowledgment length.");
    return;
  }

  noInterrupts();
  lastAcknowledgedSequence =
    static_cast<uint32_t>(data[0]) |
    (static_cast<uint32_t>(data[1]) << 8) |
    (static_cast<uint32_t>(data[2]) << 16) |
    (static_cast<uint32_t>(data[3]) << 24);
  acknowledgmentReceived = true;
  interrupts();
}
}

void initializeBle() {
  Bluefruit.begin();
  Bluefruit.setName(DEVICE_NAME);
  Bluefruit.setTxPower(0);
  Bluefruit.Periph.setConnectCallback(connectCallback);
  Bluefruit.Periph.setDisconnectCallback(disconnectCallback);

  sensorService.begin();
  sensorCharacteristic.setProperties(CHR_PROPS_NOTIFY);
  sensorCharacteristic.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  sensorCharacteristic.setMaxLen(200);
  sensorCharacteristic.begin();

  communicationService.begin();
  heartbeatCharacteristic.setProperties(CHR_PROPS_NOTIFY);
  heartbeatCharacteristic.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  heartbeatCharacteristic.setFixedLen(4);
  heartbeatCharacteristic.begin();

  acknowledgmentCharacteristic.setProperties(CHR_PROPS_WRITE);
  acknowledgmentCharacteristic.setPermission(SECMODE_OPEN, SECMODE_OPEN);
  acknowledgmentCharacteristic.setFixedLen(4);
  acknowledgmentCharacteristic.setWriteCallback(
    acknowledgmentWriteCallback
  );
  acknowledgmentCharacteristic.begin();

  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(sensorService);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);
}

bool sendSensorPacket(
  uint32_t sealId,
  uint32_t eventSequence,
  float temperature,
  bool tamper,
  float vibration
) {
  if (!Bluefruit.connected() ||
      !isfinite(temperature) ||
      !isfinite(vibration) ||
      vibration < 0.0f) {
    return false;
  }

  char authMessage[160];

  if (!formatAuthenticationMessage(
        sealId,
        eventSequence,
        temperature,
        tamper,
        vibration,
        authMessage,
        sizeof(authMessage))) {
    Serial.println("BLE: Authentication formatting failed.");
    return false;
  }

  char hmacHex[65];

  if (!generatePacketHmac(
        reinterpret_cast<const uint8_t *>(authMessage),
        strlen(authMessage),
        SMARTSEAL_HMAC_KEY,
        sizeof(SMARTSEAL_HMAC_KEY),
        hmacHex)) {
    Serial.println("BLE: HMAC generation failed.");
    return false;
  }

  char jsonPacket[256];

  const int packetLength = snprintf(
    jsonPacket,
    sizeof(jsonPacket),
    "{\"seal_id\":%lu,\"event_sequence\":%lu,"
    "\"temperature\":%.2f,\"tamper\":%s,"
    "\"vibration\":%.3f,\"hmac\":\"%s\"}",
    static_cast<unsigned long>(sealId),
    static_cast<unsigned long>(eventSequence),
    static_cast<double>(temperature),
    tamper ? "true" : "false",
    static_cast<double>(vibration),
    hmacHex
  );

  if (packetLength <= 0 ||
      packetLength >= static_cast<int>(sizeof(jsonPacket))) {
    Serial.println("BLE: Authenticated packet too large.");
    return false;
  }

  constexpr size_t FRAGMENT_SIZE = 20;

  for (size_t offset = 0;
       offset < static_cast<size_t>(packetLength);
       offset += FRAGMENT_SIZE) {

    const size_t remaining =
      static_cast<size_t>(packetLength) - offset;

    const uint16_t fragmentLength =
      static_cast<uint16_t>(
        remaining < FRAGMENT_SIZE
          ? remaining
          : FRAGMENT_SIZE
      );

    if (!sensorCharacteristic.notify(
          reinterpret_cast<const uint8_t *>(jsonPacket + offset),
          fragmentLength)) {
      Serial.println("BLE: Fragment transmission failed.");
      return false;
    }
  }

  return true;
}
void sendHeartbeat() {
  const unsigned long now = millis();
  if (!Bluefruit.connected() ||
      now - lastHeartbeatMs < HEARTBEAT_INTERVAL_MS) {
    return;
  }

  lastHeartbeatMs = now;
  ++heartbeatCounter;
  uint8_t heartbeatData[4] = {
    static_cast<uint8_t>(heartbeatCounter & 0xFF),
    static_cast<uint8_t>((heartbeatCounter >> 8) & 0xFF),
    static_cast<uint8_t>((heartbeatCounter >> 16) & 0xFF),
    static_cast<uint8_t>((heartbeatCounter >> 24) & 0xFF)
  };
  heartbeatCharacteristic.notify(heartbeatData, sizeof(heartbeatData));
}

bool getAcknowledgment(uint32_t *sequence) {
  if (sequence == nullptr || !acknowledgmentReceived) {
    return false;
  }

  noInterrupts();
  *sequence = lastAcknowledgedSequence;
  acknowledgmentReceived = false;
  interrupts();
  return true;
}
