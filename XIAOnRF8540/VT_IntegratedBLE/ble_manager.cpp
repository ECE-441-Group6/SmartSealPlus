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
constexpr uint16_t GATEWAY_MANUFACTURER_ID = 0x5353;
constexpr int SEAL_ID = 1;
BLEService recordingService(SERVICE_UUID);
BLECharacteristic dataCharacteristic(CHARACTERISTIC_UUID);
bool deviceConnected = false;
uint32_t advertisedSequence = 0;

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
  const uint8_t initialPacket[] = {
    0xA5, 1, SEAL_ID, 0, 0, 0, 0, 0, 0, 0, 0, 0
  };
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

bool publishGatewayAdvertisement(
  float temperatureC,
  bool vibrationDetected,
  uint32_t sequence
) {
  if (!isfinite(temperatureC)) {
    return false;
  }

  if (temperatureC < -3276.8f || temperatureC > 3276.7f) {
    Serial.println("WARNING: Sensor value is outside BLE packet range.");
    return false;
  }

  const int16_t temperatureTenths = static_cast<int16_t>(
    lroundf(temperatureC * 10.0f)
  );
  const uint16_t vibrationHundredths = vibrationDetected ? 100 : 0;
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
  Serial.println(vibrationDetected ? 1 : 0);
  return true;
}

bool updateGatewayAdvertisement(float temperatureC, bool vibrationDetected) {
  const uint32_t nextSequence = advertisedSequence + 1;
  if (!publishGatewayAdvertisement(
        temperatureC, vibrationDetected, nextSequence
      )) {
    return false;
  }
  advertisedSequence = nextSequence;
  return true;
}

bool isBleClientConnected() {
  return deviceConnected;
}
