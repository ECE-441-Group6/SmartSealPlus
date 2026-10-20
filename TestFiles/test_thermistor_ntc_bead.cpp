#include <math.h>

// Analog input connected to the voltage divider
const int THERMISTOR_PIN = 34;

// Thermistor specifications
const float NOMINAL_RESISTANCE = 10000.0;  // 10 kΩ at 25°C
const float NOMINAL_TEMPERATURE = 25.0;    // °C
const float BETA = 3950.0;                 // Beta value in kelvin

// Fixed resistor in the voltage divider
const float SERIES_RESISTOR = 10000.0;     // 10 kΩ

void setup() {
  Serial.begin(115200);
  delay(1000);

  analogReadResolution(12);  // 0–4095

  Serial.println("SmartSeal+ NTC Thermistor Test");
}

void loop() {
  int adcValue = analogRead(THERMISTOR_PIN);

  Serial.print("ADC reading: ");
  Serial.println(adcValue);

  // Avoid invalid calculations near the ADC limits
  if (adcValue <= 0 || adcValue >= 4095) {
    Serial.println("Invalid reading: check wiring.");
    delay(2000);
    return;
  }

  // Calculate thermistor resistance.
  // Wiring: 3V3 -> fixed resistor -> ADC -> thermistor -> GND
  float resistance =
      SERIES_RESISTOR * ((4095.0 / adcValue) - 1.0);

  // Beta equation
  float temperatureK = 1.0 /
      ((1.0 / (NOMINAL_TEMPERATURE + 273.15)) +
       (log(resistance / NOMINAL_RESISTANCE) / BETA));

  float temperatureC = temperatureK - 273.15;
  float temperatureF = temperatureC * 9.0 / 5.0 + 32.0;

  Serial.print("Thermistor resistance: ");
  Serial.print(resistance, 1);
  Serial.println(" ohms");

  Serial.print("Temperature: ");
  Serial.print(temperatureC, 2);
  Serial.print(" °C | ");

  Serial.print(temperatureF, 2);
  Serial.println(" °F");

  Serial.println("------------------------");

  delay(2000);
}
