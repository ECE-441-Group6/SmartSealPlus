
#include <bluefruit.h>
#include <math.h>
#include <string.h>
#include <stdio.h>

// ============================================================
// XIAO nRF52840 — TEMPERATURE + VIBRATION RECORDER
//
// A0 = Thermistor
// A2 = Vibration sensor
// D4 = Button 1 (start/stop)
//
// BLE packet:
// D,timestamp_ms,vibration_adc,temperature_F
//
// Gateway advertisement:
// S:1,T:temperature_F,A:0,V:vibration
//
// Temperature is "nan" if no valid reading is available.
//
// Serial Plotter:
// Temp_F:73.4 Vibration_V:1.23
//
// Set SERIAL_PLOTTER_MODE to:
// 1 = Arduino Serial Plotter output
// 0 = Detailed Serial Monitor diagnostics
// ============================================================

// Set to 1 for Arduino IDE Serial Plotter.
// Set to 0 for detailed Serial Monitor diagnostics.
#define SERIAL_PLOTTER_MODE 1

// ============================================================
// PINS
// ============================================================

const int RECORD_BUTTON_PIN = D4;
const int TEMP_PIN = A0;
const int VIBRATION_PIN = A2;

// ============================================================
// THERMISTOR CONFIGURATION
// ============================================================

const float R25 = 10000.0;
const float BETA = 3950.0;
const float T25_K = 298.15;

const float R_BOTTOM = 1000.0;
const float VCC = 3.05;
const int ADC_MAX = 4095;

// Assumed ADC full-scale reference for voltage calculation.
// Verify against your board's actual ADC reference.
const float ADC_REFERENCE_VOLTAGE = 3050;   //Milivolts

// ============================================================
// BLE CONFIGURATION
// ============================================================

#define DEVICE_NAME "Xiao_Recorder"

#define SERVICE_UUID \
  "12345678-1234-1234-1234-1234567890ab"

#define CHARACTERISTIC_UUID \
  "12345678-1234-1234-1234-1234567890ac"

const uint16_t GATEWAY_MANUFACTURER_ID = 0x5353;
const int SEAL_ID = 1;
const int VIBRATION_THRESHOLD = ADC_MAX / 2;

BLEService recordingService(SERVICE_UUID);
BLECharacteristic dataCharacteristic(CHARACTERISTIC_UUID);

bool deviceConnected = false;
bool recording = false;

// ============================================================
// SAMPLING SETTINGS
// ============================================================

const unsigned long TEMP_INTERVAL_MS = 5000;
const unsigned long VIBRATION_INTERVAL_MS = 10;
const unsigned long DEBOUNCE_MS = 40;
const unsigned long ADVERTISEMENT_INTERVAL_MS = 1000;

unsigned long lastTempSampleTime = 0;
unsigned long lastVibrationSampleTime = 0;
unsigned long lastAdvertisementTime = 0;

// Latest valid temperature, reused for vibration packets
float latestTemperatureF = NAN;

// ============================================================
// BUTTON STATE
// ============================================================

int lastButtonReading = HIGH;
int stableButtonState = HIGH;

unsigned long lastDebounceTime = 0;

// ============================================================
// BLE CALLBACKS
// ============================================================

void connect_callback(uint16_t conn_handle) {
  (void)conn_handle;

  deviceConnected = true;

  Serial.println("BLE client connected.");
}

void disconnect_callback(uint16_t conn_handle, uint8_t reason) {
  (void)conn_handle;
  (void)reason;

  deviceConnected = false;

  Serial.println("BLE client disconnected.");

  if (recording) {
    recording = false;
    Serial.println("Recording stopped due to disconnect.");
  }
}

// ============================================================
// BLE MESSAGE SENDER
// ============================================================

void sendMessage(const char* message) {
  if (!deviceConnected) return;

  size_t length = strlen(message);

  if (length > 20) {
    Serial.println("WARNING: BLE packet exceeds 20 bytes.");
    return;
  }

  dataCharacteristic.notify(
    (const uint8_t*)message,
    length
  );
}

void advertiseGatewayPacket(float temperatureF, int vibrationADC) {
  if (!isfinite(temperatureF)) return;

  char packet[24];
  int packetLength = snprintf(
    packet,
    sizeof(packet),
    "S:%d,T:%.1f,A:0,V:%d",
    SEAL_ID,
    temperatureF,
    vibrationADC >= VIBRATION_THRESHOLD ? 1 : 0
  );

  if (packetLength <= 0 || packetLength >= (int)sizeof(packet)) {
    Serial.println("WARNING: Gateway BLE packet is too long.");
    return;
  }

  uint8_t manufacturerData[sizeof(packet) + 2];
  manufacturerData[0] = (uint8_t)(GATEWAY_MANUFACTURER_ID & 0xFF);
  manufacturerData[1] = (uint8_t)(GATEWAY_MANUFACTURER_ID >> 8);
  memcpy(manufacturerData + 2, packet, packetLength);

  // The gateway scans advertisements rather than connecting to the GATT
  // characteristic. Rebuild the manufacturer field with the latest sample.
  Bluefruit.Advertising.stop();
  Bluefruit.Advertising.clearData();
  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addManufacturerData(
    manufacturerData,
    packetLength + 2
  );
  Bluefruit.ScanResponse.clearData();
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.start(0);
}

// ============================================================
// START / STOP RECORDING
// ============================================================

void startRecording() {
  if (recording) return;

  recording = true;

  unsigned long now = millis();

  // First temperature and vibration samples occur immediately.
  lastTempSampleTime = now - TEMP_INTERVAL_MS;
  lastVibrationSampleTime = now - VIBRATION_INTERVAL_MS;

  // Require a fresh temperature reading for this recording.
  latestTemperatureF = NAN;

  Serial.println("Recording started.");
  sendMessage("START\n");
}

void stopRecording() {
  if (!recording) return;

  recording = false;

  Serial.println("Recording stopped.");
  sendMessage("STOP\n");
}

// ============================================================
// TEMPERATURE CALCULATION
// ============================================================

bool readTemperature(
  float &temperatureC,
  float &temperatureF,
  int &adcValue,
  float &voltage,
  float &resistance
) {
  adcValue = analogRead(TEMP_PIN);

  voltage = ((float)adcValue / ADC_MAX) * VCC;

  // Divider: VCC -> NTC -> A0 -> 1kΩ -> GND
  if (voltage <= 0.001 || voltage >= VCC) {
    return false;
  }

  resistance = R_BOTTOM * (VCC - voltage) / voltage;

  if (resistance <= 0.0 || !isfinite(resistance)) {
    return false;
  }

  float temperatureK =
    1.0 /
    (
      (1.0 / T25_K) +
      (1.0 / BETA) * log(resistance / R25)
    );

  temperatureC = temperatureK - 273.15;
  temperatureF = temperatureC * 9.0 / 5.0 + 32.0;

  return isfinite(temperatureC) &&
         isfinite(temperatureF);
}

// ============================================================
// SERIAL OUTPUT
// ============================================================

void printPlotterValues(float temperatureF, float vibrationV) {
#if SERIAL_PLOTTER_MODE
  // Only labeled numeric values go to the Serial Plotter.
  // Timestamp is represented by sample order on its X-axis.

  Serial.print("Temp_F:");
  if (isfinite(temperatureF)) {
    Serial.print(temperatureF, 2);
  } else {
    Serial.print("nan");
  }

  Serial.print(" Vibration_V:");
  Serial.println(vibrationV, 1);
#endif
}

void printTemperatureDebug(
  unsigned long timestamp,
  int adcValue,
  float voltage,
  float resistance,
  float temperatureC,
  float temperatureF
) {
#if !SERIAL_PLOTTER_MODE
  Serial.print("TEMP | Timestamp: ");
  Serial.print(timestamp);
  Serial.print(" ms | ADC: ");
  Serial.print(adcValue);
  Serial.print(" | Voltage: ");
  Serial.print(voltage, 4);
  Serial.print(" V | Resistance: ");
  Serial.print(resistance, 1);
  Serial.print(" ohm | Temperature: ");
  Serial.print(temperatureC, 2);
  Serial.print(" C / ");
  Serial.print(temperatureF, 2);
  Serial.println(" F");
#endif
}

void printVibrationDebug(
  unsigned long timestamp,
  int adcValue,
  float voltage,
  float temperatureF
) {
#if !SERIAL_PLOTTER_MODE
  Serial.print("VIB | Timestamp: ");
  Serial.print(timestamp);
  Serial.print(" ms | ADC: ");
  Serial.print(adcValue);
  Serial.print(" | Voltage: ");
  Serial.print(voltage, 3);
  Serial.print(" V | Latest Temp: ");

  if (isfinite(temperatureF)) {
    Serial.print(temperatureF, 2);
    Serial.println(" F");
  } else {
    Serial.println("nan");
  }
#endif
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);

  unsigned long serialWaitStart = millis();

  while (!Serial &&
         millis() - serialWaitStart < 10000) {
    delay(10);
  }

  pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);
  pinMode(TEMP_PIN, INPUT);
  pinMode(VIBRATION_PIN, INPUT);

  analogReadResolution(12);

#if !SERIAL_PLOTTER_MODE
  Serial.println();
  Serial.println("XIAO Temperature + Vibration Recorder");
  Serial.println("A0 = Thermistor");
  Serial.println("A2 = Vibration");
  Serial.println("D4 = Record button");
  Serial.println("Temperature interval: 5000 ms");
  Serial.println("Vibration interval: 10 ms");
#endif

  // ----------------------------------------------------------
  // BLE INITIALIZATION
  // ----------------------------------------------------------

  Bluefruit.begin();
  Bluefruit.setName(DEVICE_NAME);

  Bluefruit.Periph.setConnectCallback(connect_callback);
  Bluefruit.Periph.setDisconnectCallback(disconnect_callback);

  recordingService.begin();

  dataCharacteristic.setProperties(
    CHR_PROPS_READ | CHR_PROPS_NOTIFY
  );

  dataCharacteristic.setPermission(
    SECMODE_OPEN,
    SECMODE_NO_ACCESS
  );

  dataCharacteristic.setMaxLen(20);
  dataCharacteristic.begin();

  dataCharacteristic.write(
    (const uint8_t*)"READY",
    5
  );

  Bluefruit.Advertising.addFlags(
    BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
  );
  Bluefruit.Advertising.addTxPower();
  const char initialGatewayPacket[] = "S:1,T:0.0,A:0,V:0";
  const size_t initialPacketLength = sizeof(initialGatewayPacket) - 1;
  uint8_t initialManufacturerData[initialPacketLength + 2];
  initialManufacturerData[0] =
    (uint8_t)(GATEWAY_MANUFACTURER_ID & 0xFF);
  initialManufacturerData[1] =
    (uint8_t)(GATEWAY_MANUFACTURER_ID >> 8);
  memcpy(
    initialManufacturerData + 2,
    initialGatewayPacket,
    initialPacketLength
  );
  Bluefruit.Advertising.addManufacturerData(
    initialManufacturerData,
    initialPacketLength + 2
  );
  Bluefruit.ScanResponse.addName();

  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);

  Serial.println("BLE advertising started.");
  Serial.println("Waiting for Raspberry Pi.");
  Serial.println("Press Button 1 to start/stop.");
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
  unsigned long now = millis();

  // ----------------------------------------------------------
  // 1. BUTTON 1 — TOGGLE RECORDING
  // ----------------------------------------------------------

  int reading = digitalRead(RECORD_BUTTON_PIN);

  if (reading != lastButtonReading) {
    lastDebounceTime = now;
    lastButtonReading = reading;
  }

  if (now - lastDebounceTime >= DEBOUNCE_MS) {
    if (reading != stableButtonState) {
      stableButtonState = reading;

      if (stableButtonState == LOW) {
        if (recording) {
          stopRecording();
        } else {
          startRecording();
        }
      }
    }
  }

  if (!recording) {
    delay(1);
    return;
  }

  now = millis();

  // ----------------------------------------------------------
  // 2. TEMPERATURE — EVERY 5 SECONDS
  // ----------------------------------------------------------

  if (now - lastTempSampleTime >= TEMP_INTERVAL_MS) {
    lastTempSampleTime = now;

    int adcValue = 0;
    float voltage = 0.0;
    float resistance = 0.0;
    float temperatureC = NAN;
    float temperatureF = NAN;

    bool valid = readTemperature(
      temperatureC,
      temperatureF,
      adcValue,
      voltage,
      resistance
    );

    if (valid) {
      latestTemperatureF = temperatureF;

      printTemperatureDebug(
        now, adcValue, voltage, resistance,
        temperatureC, temperatureF
      );
    } else {
#if !SERIAL_PLOTTER_MODE
      Serial.print("Invalid thermistor reading. ADC: ");
      Serial.println(adcValue);
#endif
    }
  }

  // ----------------------------------------------------------
  // 3. VIBRATION — EVERY 10 MILLISECONDS
  // ----------------------------------------------------------

  now = millis();

  if (now - lastVibrationSampleTime >= VIBRATION_INTERVAL_MS) {
    lastVibrationSampleTime = now;

    int vibrationADC = analogRead(VIBRATION_PIN);

    // Convert raw ADC to volts.
    float vibrationVoltage =
      ((float)vibrationADC / ADC_MAX) *
      ADC_REFERENCE_VOLTAGE;

    // --------------------------------------------------------
    // SERIAL PLOTTER
    // --------------------------------------------------------

    printPlotterValues(
      latestTemperatureF,
      vibrationVoltage
    );

    // --------------------------------------------------------
    // BLE: ONE COMBINED PACKET
    //
    // Format:
    // D,timestamp_ms,vibration_adc,temperature_F
    //
    // Example:
    // D,1234567,2048,73.4
    //
    // Temperature is "nan" if unavailable.
    // --------------------------------------------------------

    char packet[21];

    int packetLength = snprintf(
      packet,
      sizeof(packet),
      "D,%lu,%d,%.1f",
      now,
      vibrationADC,
      latestTemperatureF
    );

    // NaN is printed as "nan" by snprintf on standard
    // Arduino C libraries.
    if (packetLength > 0 && packetLength <= 20) {
      sendMessage(packet);
    }

    if (now - lastAdvertisementTime >= ADVERTISEMENT_INTERVAL_MS) {
      lastAdvertisementTime = now;
      advertiseGatewayPacket(latestTemperatureF, vibrationADC);
    }

    printVibrationDebug(
      now, vibrationADC, vibrationVoltage,
      latestTemperatureF
    );
  }

  delay(1);
}
