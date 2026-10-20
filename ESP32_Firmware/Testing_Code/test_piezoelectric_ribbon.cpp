/*
 * Test program for the SmartSeal+ vibration sensor.
 * Reads the analog value from the vibration sensor and prints it to the serial monitor.
 * One end connencts to GPIO34 (D34), the other end connects to GND.
 */

const int VIBRATION_PIN = 34;

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);

  Serial.println("SmartSeal+ Vibration Sensor Test");
}

void loop() {
  int reading = analogRead(VIBRATION_PIN);

  Serial.print("Vibration reading: ");
  Serial.println(reading);

  delay(20);
}