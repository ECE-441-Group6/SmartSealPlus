#Work in progress

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("SmartSeal+ ESP32 Hardware Test");
  Serial.println("ESP32-WROOM-32 is running!");
}

void loop() {
  Serial.println("ESP32 status: OK");
  delay(2000);
}
