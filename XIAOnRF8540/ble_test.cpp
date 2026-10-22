
#include <bluefruit.h>

const char* DEVICE_NAME = "SmartSeal-01";

BLEUart bleuart;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Bluefruit.begin();
  Bluefruit.setName(DEVICE_NAME);

  // Advertise the device name and BLE UART service.
  bleuart.begin();

  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(bleuart);
  Bluefruit.ScanResponse.addName();

  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(160, 160);
  Bluefruit.Advertising.start(0);

  Serial.println("SmartSeal-01 BLE started");
  Serial.println("Advertising BLE UART service");
}

void loop() {
  // Send a test message when a BLE central connects.
  // This is a BLE UART test; it does not broadcast
  // the message itself inside each advertisement.
  if (Bluefruit.connected()) {
    static unsigned long lastSend = 0;

    if (millis() - lastSend >= 1000) {
      lastSend = millis();
      bleuart.println("SmartSeal-01:TAMPER_OK");
      Serial.println("Sent: SmartSeal-01:TAMPER_OK");
    }
  }
}
