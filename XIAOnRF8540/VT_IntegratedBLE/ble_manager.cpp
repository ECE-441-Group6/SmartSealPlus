#include "ble_manager.h"
#include <bluefruit.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "config.h"

namespace {
constexpr char DEVICE_NAME[] = "SmartSeal-XIAO";
constexpr char SERVICE_UUID[] = "12345678-1234-1234-1234-1234567890ab";
constexpr char CHARACTERISTIC_UUID[] = "12345678-1234-1234-1234-1234567890ac";
constexpr char ACK_SERVICE_UUID[] = "12345678-1234-1234-1234-1234567890ad";
constexpr char ACK_CHARACTERISTIC_UUID[] = "12345678-1234-1234-1234-1234567890ae";
constexpr uint16_t GATEWAY_MANUFACTURER_ID = 0x5353;
constexpr int SEAL_ID = 1;
BLEService recordingService(SERVICE_UUID);
BLECharacteristic dataCharacteristic(CHARACTERISTIC_UUID);
BLEService xiaoService(ACK_SERVICE_UUID);
BLECharacteristic xiaoCharacteristic(ACK_CHARACTERISTIC_UUID);
bool deviceConnected = false;
volatile bool gatewayAcknowledged = false;
volatile uint32_t acknowledgedSequence = 0;
uint32_t advertisedSequence = 0;

void gatewayAckCallback(
  uint16_t connHandle,
  BLECharacteristic *characteristic,
  uint8_t *data,
  uint16_t len
) {
  (void)connHandle;
  (void)characteristic;
  unsigned int sealId = 0;
  unsigned long sequence = 0;
  char ack[24] = {};
  if (len >= sizeof(ack)) {
    return;
  }
  memcpy(ack, data, len);
  if (sscanf(ack, "ACK:S:%u,E:%lu", &sealId, &sequence) == 2 &&
      sealId == SEAL_ID && sequence == advertisedSequence) {
    acknowledgedSequence = static_cast<uint32_t>(sequence);
    gatewayAcknowledged = true;
  }
}

void connectCallback(uint16_t connHandle) {
  (void)connHandle;
  deviceConnected = true;
  Serial.println("BLE client connected.");
}

void disconnectCallback(uint16_t connHandle, uint8_t reason) {
  (void)connHandle;
  (void)reason;
  deviceConnected = false;
  Serial.println("BLE client disconnected; XIAO advertising will restart.");
}

void addGatewayManufacturerData(const uint8_t *packet, int packetLength) {
  uint8_t manufacturerData[29];
  manufacturerData[0] = (uint8_t)(GATEWAY_MANUFACTURER_ID & 0xFF);
  manufacturerData[1] = (uint8_t)(GATEWAY_MANUFACTURER_ID >> 8);
  memcpy(manufacturerData + 2, packet, packetLength);
  Bluefruit.Advertising.addManufacturerData(
    manufacturerData,
    packetLength + 2
  );
}
}

void initializeBle() {
  Bluefruit.begin();
  Bluefruit.setName(DEVICE_NAME);
  Bluefruit.Periph.setConnectCallback(connectCallback);
  Bluefruit.Periph.setDisconnectCallback(disconnectCallback);

  recordingService.begin();
  dataCharacteristic.setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY);
  dataCharacteristic.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  dataCharacteristic.setMaxLen(32);
  dataCharacteristic.begin();
  dataCharacteristic.write((const uint8_t *)"READY", 5);
  xiaoService.begin();
  xiaoCharacteristic.setProperties(
    CHR_PROPS_READ | CHR_PROPS_NOTIFY | CHR_PROPS_WRITE
  );
  xiaoCharacteristic.setPermission(SECMODE_OPEN, SECMODE_OPEN);
  xiaoCharacteristic.setMaxLen(32);
  xiaoCharacteristic.setWriteCallback(gatewayAckCallback);
  xiaoCharacteristic.begin();
  const uint8_t initialPacket[] = {
    0xA5, 1, SEAL_ID, 0, 0, 0, 0, 0, 0, 0, 0, 0
  };
  xiaoCharacteristic.write(
    initialPacket,
    sizeof(initialPacket)
  );

  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  addGatewayManufacturerData(initialPacket, sizeof(initialPacket));
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);
  Serial.print("XIAO is advertising as ");
  Serial.print(DEVICE_NAME);
  Serial.println(".");
}

void sendBleMessage(const char *message) {
  if (!deviceConnected) {
    return;
  }

  const size_t length = strlen(message);
  if (length > 20) {
    Serial.println("WARNING: BLE packet exceeds 20 bytes.");
    return;
  }
  dataCharacteristic.notify((const uint8_t *)message, length);
}

void publishGatewayAdvertisement(
  float temperatureC,
  float vibrationVoltage,
  uint32_t sequence
) {
  if (!isfinite(temperatureC)) {
    return;
  }

  if (temperatureC < -3276.8f || temperatureC > 3276.7f ||
      vibrationVoltage < 0.0f || vibrationVoltage > 655.35f) {
    Serial.println("WARNING: Sensor value is outside BLE packet range.");
    return;
  }

  const int16_t temperatureTenths = static_cast<int16_t>(
    lroundf(temperatureC * 10.0f)
  );
  const uint16_t vibrationHundredths = static_cast<uint16_t>(
    lroundf(vibrationVoltage * 100.0f)
  );
  const uint8_t packet[12] = {
    0xA5,
    1,
    static_cast<uint8_t>(SEAL_ID),
    static_cast<uint8_t>(sequence & 0xFF),
    static_cast<uint8_t>((sequence >> 8) & 0xFF),
    static_cast<uint8_t>((sequence >> 16) & 0xFF),
    static_cast<uint8_t>((sequence >> 24) & 0xFF),
    static_cast<uint8_t>(temperatureTenths & 0xFF),
    static_cast<uint8_t>((temperatureTenths >> 8) & 0xFF),
    static_cast<uint8_t>(
      temperatureC < 2.0f || temperatureC > 8.0f ? 1 : 0
    ),
    static_cast<uint8_t>(vibrationHundredths & 0xFF),
    static_cast<uint8_t>((vibrationHundredths >> 8) & 0xFF)
  };

  xiaoCharacteristic.write(packet, sizeof(packet));
  if (deviceConnected) {
    xiaoCharacteristic.notify(packet, sizeof(packet));
  }

  Bluefruit.Advertising.stop();
  Bluefruit.Advertising.clearData();
  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  addGatewayManufacturerData(packet, sizeof(packet));
  Bluefruit.ScanResponse.clearData();
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.start(0);
  Serial.print("XIAO advertisement updated: ");
  Serial.print("S:");
  Serial.print(SEAL_ID);
  Serial.print(",E:");
  Serial.print(sequence);
  Serial.print(",T:");
  Serial.print(temperatureC, 1);
  Serial.print(",A:");
  Serial.print(temperatureC < 2.0f || temperatureC > 8.0f ? 1 : 0);
  Serial.print(",V:");
  Serial.println(vibrationVoltage, 2);
}

void updateGatewayAdvertisement(float temperatureC, float vibrationVoltage) {
  publishGatewayAdvertisement(temperatureC, vibrationVoltage, ++advertisedSequence);
}

void repeatGatewayAdvertisement(float temperatureC, float vibrationVoltage) {
  publishGatewayAdvertisement(temperatureC, vibrationVoltage, advertisedSequence);
}

bool isBleClientConnected() {
  return deviceConnected;
}

bool waitForGatewayAcknowledgement() {
  gatewayAcknowledged = false;
  const unsigned long start = millis();
  while (!gatewayAcknowledged &&
         millis() - start < ACK_TIMEOUT_MS) {
    delay(10);
  }
  if (!gatewayAcknowledged) {
    Serial.println("Gateway acknowledgment timeout; retrying packet.");
  }
  return gatewayAcknowledged && acknowledgedSequence == advertisedSequence;
}
