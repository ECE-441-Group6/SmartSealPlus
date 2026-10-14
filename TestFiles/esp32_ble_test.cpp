// This code is for testing BLE advertising on the ESP32. It sets up the ESP32 to advertise a BLE device with a specific name and manufacturer data payload.
// After uploading this code to the ESP32, run verify_smartseal_ble.py on the Raspberry Pi to confirm that the BLE advertising is working correctly.
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>

BLEAdvertising *advertising;

void updateAdvertisement(String message) {
  // Stop advertising before changing the payload
  advertising->stop();

  BLEAdvertisementData advertData;
  advertData.setName("SmartSeal-01");

  // Test manufacturer ID: 0xFFFF
  String payload = "";
  payload += (char)0xFF;
  payload += (char)0xFF;
  payload += message;

  advertData.setManufacturerData(payload);

  advertising->setAdvertisementData(advertData);
  advertising->start();

  Serial.print("Broadcast message: ");
  Serial.println(message);
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(1000);
  delay(1000);

  BLEDevice::init("SmartSeal-01");
  advertising = BLEDevice::getAdvertising();

  updateAdvertisement("READY");

  Serial.println();
  Serial.println("SmartSeal+ BLE Message Test");
  Serial.println("Type a message and press Enter.");
  Serial.println("Keep messages short for BLE advertising.");
}

void loop() {
  if (Serial.available()) {
    String message = Serial.readStringUntil('\n');
    message.trim();

    if (message.length() > 0) {
      // Keep the payload small to fit legacy BLE advertising.
      // The device name and BLE packet overhead use space too.
      if (message.length() > 8) {
        message = message.substring(0, 8);
        Serial.println("Message shortened to 8 characters.");
      }

      updateAdvertisement(message);
    }
  }

  delay(10);
}

