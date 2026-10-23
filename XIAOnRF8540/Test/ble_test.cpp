//Run with xiaobletest.py in Gateway/Test folder
#include <bluefruit.h>

BLEService smartSealService(
    0x180F
);

BLECharacteristic messageCharacteristic(
    0x2A19
);

int messageCount = 0;
unsigned long lastSendTime = 0;

void connect_callback(uint16_t conn_handle) {
  Serial.println("Raspberry Pi connected!");
}

void disconnect_callback(uint16_t conn_handle, uint8_t reason) {
  Serial.println("Raspberry Pi disconnected!");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("Starting XIAO BLE...");

  Bluefruit.begin();
  Bluefruit.setName("SmartSeal-XIAO");

  Bluefruit.Periph.setConnectCallback(connect_callback);
  Bluefruit.Periph.setDisconnectCallback(disconnect_callback);

  smartSealService.begin();

  messageCharacteristic.setProperties(
      CHR_PROPS_READ | CHR_PROPS_NOTIFY
  );
  messageCharacteristic.setPermission(
      SECMODE_OPEN, SECMODE_NO_ACCESS
  );
  messageCharacteristic.setMaxLen(20);
  messageCharacteristic.begin();
  messageCharacteristic.write("BLE_READY");

  Bluefruit.Advertising.addFlags(
      BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(smartSealService);
  Bluefruit.Advertising.addName();

  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.start(0);

  Serial.println("Advertising as SmartSeal-XIAO");
}

void loop() {
  if (millis() - lastSendTime >= 2000) {
    lastSendTime = millis();

    char message[20];
    snprintf(message, sizeof(message), "Hello_%d", messageCount++);

    messageCharacteristic.write(message);

    if (Bluefruit.connected()) {
      messageCharacteristic.notify(message);
    }

    Serial.print("Current message: ");
    Serial.println(message);
  }
}
