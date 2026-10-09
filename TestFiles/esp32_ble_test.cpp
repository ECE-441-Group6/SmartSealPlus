// This code is for testing BLE advertising on the ESP32. It sets up the ESP32 to advertise a BLE device with a specific name and manufacturer data payload.
// After uploading this code to the ESP32, run verify_smartseal_ble.py on the Raspberry Pi to confirm that the BLE advertising is working correctly.
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>

BLEAdvertising *advertising;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("SmartSeal+ BLE Advertising Test");

  BLEDevice::init("SmartSeal-01");

  BLEAdvertisementData advertData;
  advertData.setName("SmartSeal-01");

  String payload = "";
  payload += (char)0xFF;
  payload += (char)0xFF;
  payload += "SSTesting";

  advertData.setManufacturerData(payload);

  advertising = BLEDevice::getAdvertising();
  advertising->setAdvertisementData(advertData);
  advertising->start();

  Serial.println("BLE advertising started.");
  Serial.println("Device name: SmartSeal-01");
  Serial.println("Test payload: SSP:TEST:OK");
}

void loop() {
  delay(5000);
  Serial.println("BLE advertising is running.");
}
