// PUI Audio AI-3435-TF-LW140-R
// ESP32 Active Buzzer Test

const int BUZZER_PIN = 18;

void setup() {
  Serial.begin(115200);

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.println("Starting buzzer test...");
}

void loop() {
  // Turn buzzer ON
  digitalWrite(BUZZER_PIN, HIGH);
  Serial.println("BUZZER ON");
  delay(1000);

  // Turn buzzer OFF
  digitalWrite(BUZZER_PIN, LOW);
  Serial.println("BUZZER OFF");
  delay(1000);
}