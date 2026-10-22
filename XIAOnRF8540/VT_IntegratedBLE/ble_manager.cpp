#include "ble_manager.h"

#include <bluefruit.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "config.h"

namespace {
constexpr char DEVICE_NAME[] = "Xiao_Recorder";
constexpr char SERVICE_UUID[] = "12345678-1234-1234-1234-1234567890ab";
constexpr char CHARACTERISTIC_UUID[] = "12345678-1234-1234-1234-1234567890ac";
constexpr uint16_t GATEWAY_MANUFACTURER_ID = 0x5353;
constexpr int SEAL_ID = 1;
constexpr int VIBRATION_THRESHOLD = ADC_MAX / 2;

BLEService recordingService(SERVICE_UUID);
BLECharacteristic dataCharacteristic(CHARACTERISTIC_UUID);
bool deviceConnected = false;

void connectCallback(uint16_t connHandle) {
  (void)connHandle;
  deviceConnected = true;
  Serial.println("BLE client connected.");
}

void disconnectCallback(uint16_t connHandle, uint8_t reason) {
  (void)connHandle;
  (void)reason;
  deviceConnected = false;
  Serial.println("BLE client disconnected.");
}

void addGatewayManufacturerData(const char *packet, int packetLength) {
  uint8_t manufacturerData[32];
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
  dataCharacteristic.setMaxLen(20);
  dataCharacteristic.begin();
  dataCharacteristic.write((const uint8_t *)"READY", 5);

  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  const char initialPacket[] = "S:1,T:0.0,A:0,V:0";
  addGatewayManufacturerData(initialPacket, sizeof(initialPacket) - 1);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);
  Serial.println("BLE advertising started.");
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

void updateGatewayAdvertisement(float temperatureF, int vibrationADC) {
  if (!isfinite(temperatureF)) {
    return;
  }

  char packet[24];
  const int packetLength = snprintf(
    packet,
    sizeof(packet),
    "S:%d,T:%.1f,A:0,V:%d",
    SEAL_ID,
    temperatureF,
    vibrationADC >= VIBRATION_THRESHOLD ? 1 : 0
  );
  if (packetLength <= 0 || packetLength >= (int)sizeof(packet)) {
    Serial.println("WARNING: Gateway BLE packet is too long.");
    return;
  }

  Bluefruit.Advertising.stop();
  Bluefruit.Advertising.clearData();
  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  addGatewayManufacturerData(packet, packetLength);
  Bluefruit.ScanResponse.clearData();
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.start(0);
}

bool isBleClientConnected() {
  return deviceConnected;
}
