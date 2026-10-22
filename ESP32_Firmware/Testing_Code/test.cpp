// Reproducible ESP32 event simulation
//Run python3 test.py on Raspberry Pi to test event handling. The ESP32 will broadcast BLE events based on the input from the serial console.
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>

BLEAdvertising* advertising;
const char* DEVICE_NAME = "SmartSeal-01";

void sendEvent(const char* event) {
  // Company ID 0xFFFF followed by event text
  String payload;
  payload += (char)0xFF;
  payload += (char)0xFF;
  payload += event;

  BLEAdvertisementData data;
  data.setFlags(0x06);
  data.setName(DEVICE_NAME);
  data.setManufacturerData(payload);

  advertising->stop();
  advertising->setAdvertisementData(data);
  advertising->start();

  Serial.print("Broadcasting: ");
  Serial.println(event);
}

void setup() {
  Serial.begin(115200);

  BLEDevice::init(DEVICE_NAME);
  advertising = BLEDevice::getAdvertising();

  sendEvent("NORMAL");

  Serial.println("BLE simulation ready.");
  Serial.println("Enter NORMAL, TAMPER, HIGH, or LOW.");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if (cmd == "NORMAL") {
      sendEvent("NORMAL");
    } else if (cmd == "TAMPER") {
      sendEvent("TAMPER1");
    } else if (cmd == "HIGH") {
      sendEvent("TEMPHIGH");
    } else if (cmd == "LOW") {
      sendEvent("TEMPLOW");
    } else {
      Serial.println("Unknown command.");
    }
  }

  delay(20);
}
