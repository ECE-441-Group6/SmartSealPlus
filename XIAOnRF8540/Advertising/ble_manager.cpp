#include "ble_manager.h"

#include <bluefruit.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

#include "config.h"

namespace {
constexpr char DEVICE_NAME[] = "Xiao_Recorder";
constexpr uint16_t GATEWAY_MANUFACTURER_ID = 0x5353;
constexpr uint8_t PACKET_VERSION = 1;
constexpr uint8_t SEAL_ID = 1;

uint32_t advertisementSequence = 0;

void addManufacturerPacket(const uint8_t *packet, size_t packetLength) {
  uint8_t manufacturerData[14];
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
}

void initializeBle() {
  Bluefruit.begin();
  Bluefruit.setName(DEVICE_NAME);

  const uint8_t initialPacket[12] = {
    0xA5, PACKET_VERSION, SEAL_ID,
    0, 0, 0, 0,
    0, 0,
    0,
    0, 0
  };

  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  addManufacturerPacket(initialPacket, sizeof(initialPacket));
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);

  Serial.println("BLE manufacturer advertising started.");
  Serial.print("Device name: ");
  Serial.println(DEVICE_NAME);
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
  const uint32_t sequence = ++advertisementSequence;

  const uint8_t packet[12] = {
    0xA5,
    PACKET_VERSION,
    SEAL_ID,
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

  Bluefruit.Advertising.stop();
  Bluefruit.Advertising.clearData();
  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  addManufacturerPacket(packet, sizeof(packet));
  Bluefruit.ScanResponse.clearData();
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.start(0);

  Serial.print("Advertisement updated: sequence=");
  Serial.print(sequence);
  Serial.print(", temperature C=");
  Serial.print(temperatureC, 1);
  Serial.print(", vibration=");
  Serial.println(vibrationDetected ? 1 : 0);
  return true;
}
