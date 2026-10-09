// ===========================================================
// XIAO nRF52840
// Vishay Ametherm PANE103395 NTC Thermistor
//
// Voltage divider:
//
//       3.3 V
//         |
//         |
//       NTC
//     10 kΩ @ 25°C
//         |
//         +-------- ADC
//         |
//       26 kΩ
//         |
//        GND
//
// Reads the ADC every 5 seconds and calculates temperature.
// ===========================================================


// ===========================================================
// ADC PIN
// ===========================================================

#define ANALOG_PIN A0


// ===========================================================
// THERMISTOR CONSTANTS
// ===========================================================

// PANE103395:
// Resistance at 25°C
const float R25 = 10000.0;


// Beta value from Ametherm datasheet
const float BETA = 3950.0;


// Reference temperature:
// 25°C in Kelvin
const float T25_K = 298.15;


// Fixed resistor in voltage divider
const float R_FIXED = 26000.0;


// Supply voltage
const float VCC = 3.3;


// ADC resolution
const int ADC_MAX = 4095;


// ===========================================================
// SETUP
// ===========================================================

void setup() {

  Serial.begin(115200);

  delay(500);


  // 12-bit ADC
  //
  // Raw ADC:
  // 0    = minimum
  // 4095 = maximum
  analogReadResolution(12);


  pinMode(ANALOG_PIN, INPUT);


  Serial.println();
  Serial.println("=================================");
  Serial.println("XIAO nRF52840 NTC Temperature");
  Serial.println("Vishay Ametherm PANE103395");
  Serial.println("=================================");
  Serial.println();

  Serial.println("Divider:");
  Serial.println("3.3V -> NTC -> ADC -> 26k -> GND");
  Serial.println();

  Serial.println("Reading temperature every 5 seconds...");
  Serial.println();
}


// ===========================================================
// MAIN LOOP
// ===========================================================

void loop() {


  // ---------------------------------------------------------
  // READ ADC
  // ---------------------------------------------------------

  int adcValue = analogRead(ANALOG_PIN);


  // ---------------------------------------------------------
  // CONVERT ADC READING TO VOLTAGE
  // ---------------------------------------------------------

  float voltage =
    ((float)adcValue / (float)ADC_MAX) * VCC;


  // ---------------------------------------------------------
  // CALCULATE NTC RESISTANCE
  //
  // Voltage divider:
  //
  //       VCC
  //        |
  //       R_NTC
  //        |
  //        +---- VADC
  //        |
  //       R_FIXED
  //        |
  //       GND
  //
  // VADC = VCC * R_FIXED / (R_NTC + R_FIXED)
  //
  // Therefore:
  //
  // R_NTC = R_FIXED * (VCC/VADC - 1)
  // ---------------------------------------------------------

  float resistance;


  // Prevent division by zero if ADC reads 0
  if (voltage > 0.001) {

    resistance =
      R_FIXED * ((VCC / voltage) - 1.0);
  }

  else {

    resistance = 999999999.0;
  }


  // ---------------------------------------------------------
  // CALCULATE TEMPERATURE
  //
  // Beta equation:
  //
  // 1/T = 1/T25 + (1/BETA) * ln(R/R25)
  //
  // Temperature returned in Kelvin.
  // ---------------------------------------------------------

  float temperature_K =
    1.0 /
    (
      (1.0 / T25_K) +
      (1.0 / BETA) *
      log(resistance / R25)
    );


  // Convert Kelvin to Celsius
  float temperature_C =
    temperature_K - 273.15;


  // ---------------------------------------------------------
  // PRINT RESULTS
  // ---------------------------------------------------------

  Serial.print("ADC: ");
  Serial.print(adcValue);

  Serial.print("    Voltage: ");
  Serial.print(voltage, 4);
  Serial.print(" V");

  Serial.print("    Resistance: ");
  Serial.print(resistance, 1);
  Serial.print(" ohm");

  Serial.print("    Temperature: ");
  Serial.print(temperature_C, 2);
  Serial.println(" °C");


  // ---------------------------------------------------------
  // WAIT 5 SECONDS
  // ---------------------------------------------------------

  delay(5000);
}