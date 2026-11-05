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
constexpr size_t PACKET_LENGTH = 11;
constexpr int16_t INVALID_TEMPERATURE = INT16_MAX;

uint32_t advertisementSequence = 0;

bool addManufacturerPacket(const uint8_t *packet) {
  uint8_t manufacturerData[2 + PACKET_LENGTH] = {
    static_cast<uint8_t>(GATEWAY_MANUFACTURER_ID & 0xFF),
    static_cast<uint8_t>(GATEWAY_MANUFACTURER_ID >> 8)
  };
  memcpy(manufacturerData + 2, packet, PACKET_LENGTH);
  return Bluefruit.Advertising.addManufacturerData(
    manufacturerData,
    sizeof(manufacturerData)
  );
}

bool makePacket(
  float temperatureC,
  bool vibrationDetected,
  uint32_t sequence,
  uint8_t *packet
) {
  if (!packet) {
    return false;
  }

  int16_t temperatureTenths = INVALID_TEMPERATURE;
  if (isfinite(temperatureC)) {
    if (temperatureC < -3276.8f || temperatureC > 3276.6f) {
      return false;
    }
    temperatureTenths =
      static_cast<int16_t>(lroundf(temperatureC * 10.0f));
  }

  packet[0] = PACKET_VERSION;
  packet[1] = SEAL_ID;
  packet[2] = static_cast<uint8_t>(sequence & 0xFF);
  packet[3] = static_cast<uint8_t>((sequence >> 8) & 0xFF);
  packet[4] = static_cast<uint8_t>((sequence >> 16) & 0xFF);
  packet[5] = static_cast<uint8_t>((sequence >> 24) & 0xFF);
  packet[6] = static_cast<uint8_t>(temperatureTenths & 0xFF);
  packet[7] = static_cast<uint8_t>(
    (static_cast<uint16_t>(temperatureTenths) >> 8) & 0xFF
  );
  packet[8] = 0;
  const uint16_t vibrationHundredths = vibrationDetected ? 100 : 0;
  packet[9] = static_cast<uint8_t>(vibrationHundredths & 0xFF);
  packet[10] = static_cast<uint8_t>(vibrationHundredths >> 8);
  return true;
}
}

bool initializeBle() {
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
  Serial.println("Press D6 to start sensor broadcasts.");
  return true;
}

bool updateGatewayAdvertisement(
  float temperatureC,
  bool vibrationDetected
) {
  const uint32_t sequence = ++advertisementSequence;
  uint8_t packet[PACKET_LENGTH];
  if (!makePacket(temperatureC, vibrationDetected, sequence, packet)) {
    Serial.println("ERROR: Sensor values do not fit BLE packet.");
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
      !addManufacturerPacket(packet)) {
    Serial.println("ERROR: Could not build BLE manufacturer packet.");
    return false;
  }
  if (!Bluefruit.Advertising.start(0)) {
    Serial.println("ERROR: Could not resume BLE advertising.");
    return false;
  }

  Serial.print("BLE advertisement sent: sequence=");
  Serial.print(sequence);
  Serial.print(", temperature C=");
  if (isfinite(temperatureC)) {
    Serial.print(temperatureC, 1);
  } else {
    Serial.print("invalid");
  }
  Serial.print(", vibration=");
  Serial.println(vibrationDetected ? 1 : 0);
  return true;
}
