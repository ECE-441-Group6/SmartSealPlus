#include <bluefruit.h>
#include <math.h>
#include <string.h>
#include <stdio.h>

// ===========================================================
// XIAO nRF52840 — THERMISTOR TESTER
//
// Voltage divider:
//
//       3.05 V
//         |
//       NTC Thermistor
//         |
//         +-------- A0
//         |
//         1 kΩ
//         |
//        GND
//
// Reads temperature every 5 seconds.
// Displays temperature in Celsius and Fahrenheit.
// ===========================================================

// ADC PIN
const int ANALOG_PIN = A0;

// THERMISTOR CONSTANTS
// Vishay Ametherm PANE103395-ND
const float R25 = 10000.0;   // Resistance at 25°C (ohms)
const float BETA = 3950.0;   // Beta value (K)
const float T25_K = 298.15;  // 25°C in Kelvin

// VOLTAGE DIVIDER CONSTANTS
const float R_BOTTOM = 1000.0;  // 1 kΩ
const float VCC = 3.05;

const int ADC_MAX = 4095;

const unsigned long SAMPLE_INTERVAL_MS = 5000;
unsigned long lastSampleTime = 0;

// ===========================================================
// SETUP
// ===========================================================

void setup() {
  Serial.begin(115200);

  // Wait up to 10 seconds for Serial Monitor.
  unsigned long serialWaitStart = millis();

  while (!Serial &&
         millis() - serialWaitStart < 10000) {
    delay(10);
  }

  delay(200);

  Serial.println();
  Serial.println("=================================");
  Serial.println("XIAO nRF52840 Thermistor Tester");
  Serial.println("Vishay Ametherm PANE103395-ND");
  Serial.println("=================================");

  pinMode(ANALOG_PIN, INPUT);
  analogReadResolution(12);

  Serial.println(
      "Divider: 3.05V -> NTC -> A0 -> 1k -> GND"
  );
  Serial.println("Sampling interval: 5 seconds");
  Serial.println("Temperature: Celsius and Fahrenheit");
  Serial.println();

  lastSampleTime = millis();
}

// ===========================================================
// MAIN LOOP
// ===========================================================

void loop() {
  if (millis() - lastSampleTime < SAMPLE_INTERVAL_MS) {
    delay(1);
    return;
  }

  lastSampleTime = millis();

  // ---------------------------------------------------------
  // 1. READ ADC
  // ---------------------------------------------------------

  int adcValue = analogRead(ANALOG_PIN);

  // ---------------------------------------------------------
  // 2. CONVERT ADC READING TO VOLTAGE
  // ---------------------------------------------------------

  float voltage =
      ((float)adcValue / (float)ADC_MAX) * VCC;

  // ---------------------------------------------------------
  // 3. CALCULATE THERMISTOR RESISTANCE
  //
  // Divider:
  // VCC -> R_NTC -> A0 -> R_BOTTOM -> GND
  //
  // R_NTC = R_BOTTOM * (VCC - VADC) / VADC
  // ---------------------------------------------------------

  float resistance = -1.0;

  if (voltage > 0.001 && voltage < VCC) {
    resistance =
        R_BOTTOM * (VCC - voltage) / voltage;
  }

  // ---------------------------------------------------------
  // 4. CALCULATE TEMPERATURE USING BETA EQUATION
  // ---------------------------------------------------------

  float temperatureC = NAN;
  float temperatureF = NAN;

  if (resistance > 0.0 && BETA > 0.0) {
    float temperatureK =
        1.0 /
        (
          (1.0 / T25_K) +
          (1.0 / BETA) * log(resistance / R25)
        );

    temperatureC = temperatureK - 273.15;

    // Convert Celsius to Fahrenheit.
    temperatureF = (temperatureC * 9.0 / 5.0) + 32.0;
  }

  // ---------------------------------------------------------
  // 5. PRINT RESULTS
  // ---------------------------------------------------------

  Serial.print("ADC: ");
  Serial.print(adcValue);

  Serial.print(" | Voltage: ");
  Serial.print(voltage, 4);
  Serial.print(" V");

  Serial.print(" | Resistance: ");

  if (resistance > 0.0 &&
      isfinite(temperatureC) &&
      isfinite(temperatureF)) {

    Serial.print(resistance, 1);
    Serial.print(" ohm");

    Serial.print(" | Temperature: ");
    Serial.print(temperatureC, 2);
    Serial.print(" C");

    Serial.print(" / ");
    Serial.print(temperatureF, 2);
    Serial.println(" F");

  } else {
    Serial.println(
        "Invalid reading; check wiring and ADC voltage."
    );
  }
}