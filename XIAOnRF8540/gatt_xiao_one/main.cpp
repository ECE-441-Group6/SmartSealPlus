#include <Arduino.h>
#include <math.h>

#include "Thermistor.h"
#include "Vibration.h"

// Bluetooth functions implemented in GATT_Xiao.ino.
void setupBLE();
void sendHeartbeat();

bool sendSensorPacket(
    uint32_t sealID,
    uint32_t eventSequence,
    float temperature,
    bool tamper,
    float vibration
);

bool getAcknowledgment(uint32_t* sequence);

// ============================================================
// CONFIGURATION
// ============================================================

static const int RECORD_BUTTON_PIN = D6;

static const uint32_t SEAL_ID = 1;

// All sensors are sampled together at this rate.
static const unsigned long SENSOR_SAMPLING_INTERVAL_MS = 100;

// BLE transmission has its own independent timing setting.
static const unsigned long BLE_TRANSMISSION_INTERVAL_MS = 100;

static const unsigned long BUTTON_DEBOUNCE_MS = 40;

static const int ADC_MAX_VALUE = 4095;

// Placeholder threshold inherited from the original recorder.
// Tune this using actual vibration measurements.
static const int VIBRATION_THRESHOLD = ADC_MAX_VALUE / 2;

// ============================================================
// SENSOR DATA
// ============================================================

struct SensorReadings {
    unsigned long timestampMs;
    float temperatureC;
    float temperatureF;
    int vibrationADC;
    float vibrationVoltage;
    bool temperatureValid;
};

static SensorReadings latestReadings = {
    0, NAN, NAN, 0, 0.0f, false
};

// ============================================================
// PROGRAM STATE
// ============================================================

static bool recording = false;

static unsigned long lastSensorSampleMs = 0;
static unsigned long lastBLETransmissionMs = 0;

static uint32_t eventSequence = 0;

// Button debounce state.
static int lastButtonReading = HIGH;
static int stableButtonState = HIGH;
static unsigned long lastDebounceMs = 0;

// ============================================================
// BUTTON CONTROL
// ============================================================

static void startRecording() {
    if (recording) {
        return;
    }

    recording = true;

    // Schedule the first sensor sample and transmission immediately.
    unsigned long now = millis();
    lastSensorSampleMs =
        now - SENSOR_SAMPLING_INTERVAL_MS;
    lastBLETransmissionMs =
        now - BLE_TRANSMISSION_INTERVAL_MS;

    // Require a fresh temperature reading.
    latestReadings.temperatureC = NAN;
    latestReadings.temperatureF = NAN;
    latestReadings.temperatureValid = false;

    Serial.println("Recording started.");
}

static void stopRecording() {
    if (!recording) {
        return;
    }

    recording = false;
    Serial.println("Recording stopped.");
}

static void updateRecordButton(unsigned long now) {
    int reading = digitalRead(RECORD_BUTTON_PIN);

    if (reading != lastButtonReading) {
        lastDebounceMs = now;
        lastButtonReading = reading;
    }

    if (now - lastDebounceMs >= BUTTON_DEBOUNCE_MS) {
        if (reading != stableButtonState) {
            stableButtonState = reading;

            // INPUT_PULLUP: LOW means pressed.
            if (stableButtonState == LOW) {
                if (recording) {
                    stopRecording();
                } else {
                    startRecording();
                    
                }
            }
        }
    }
}

// ============================================================
// SETUP
// ============================================================

void setup() {
    Serial.begin(115200);

    unsigned long serialStartMs = millis();

    while (!Serial &&
           millis() - serialStartMs < 10000) {
        delay(10);
    }

    pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);

    analogReadResolution(12);

    // Initialize the sensor modules.
    thermistorBegin();
    vibrationBegin();

    // Initialize BLE services and advertising.
    setupBLE();

    Serial.println();
    Serial.println("SmartSeal recorder ready.");
    Serial.println("A0: Thermistor");
    Serial.println("A2: Vibration sensor");
    Serial.println("D4: Record button");
    Serial.print("Sensor sampling interval: ");
    Serial.print(SENSOR_SAMPLING_INTERVAL_MS);
    Serial.println(" ms");
    Serial.print("BLE transmission interval: ");
    Serial.print(BLE_TRANSMISSION_INTERVAL_MS);
    Serial.println(" ms");
}

// ============================================================
// SAMPLE ALL SENSORS TOGETHER
// ============================================================

static void sampleAllSensors(unsigned long now) {
    // Record the time associated with this sensor update.
    latestReadings.timestampMs = now;

    // ------------------------
    // Temperature
    // ------------------------

    float temperatureC = NAN;
    float temperatureF = NAN;

    bool validTemperature =
        readThermistor(temperatureC, temperatureF);

    latestReadings.temperatureValid = validTemperature;

    if (validTemperature) {
        latestReadings.temperatureC = temperatureC;
        latestReadings.temperatureF = temperatureF;
    } else {
        latestReadings.temperatureC = NAN;
        latestReadings.temperatureF = NAN;
    }

    // ------------------------
    // Vibration
    // ------------------------

    latestReadings.vibrationADC = readVibrationADC();

    latestReadings.vibrationVoltage =
        vibrationADCToVolts(
            latestReadings.vibrationADC
        );

    // Both sensor readings now belong to this update.
    Serial.print("Sample time: ");
    Serial.print(latestReadings.timestampMs);
    Serial.print(" ms | Temp F: ");

    if (latestReadings.temperatureValid) {
        Serial.print(latestReadings.temperatureF, 2);
    } else {
        Serial.print("invalid");
    }

    Serial.print(" | Vibration ADC: ");
    Serial.print(latestReadings.vibrationADC);

    Serial.print(" | Vibration V: ");
    Serial.println(latestReadings.vibrationVoltage, 3);
}

// ============================================================
// BLE TRANSMISSION
// ============================================================

static void transmitLatestReadings() {
    bool tamperDetected =
        latestReadings.vibrationADC >= VIBRATION_THRESHOLD;

    bool sent = sendSensorPacket(
        SEAL_ID,
        eventSequence,
        latestReadings.temperatureValid
            ? latestReadings.temperatureF
            : NAN,
        tamperDetected,
        latestReadings.vibrationVoltage
    );

    // Advance the sequence only if the notification was sent.
    if (sent) {
        eventSequence++;
    }

    // Check for an acknowledgment from the Raspberry Pi.
    uint32_t acknowledgedSequence = 0;

    if (getAcknowledgment(&acknowledgedSequence)) {
        Serial.print("Pi acknowledged sequence: ");
        Serial.println(acknowledgedSequence);
    }
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
    unsigned long now = millis();

    // Keep the button responsive whether recording or not.
    updateRecordButton(now);

    // Heartbeat timing is managed independently by the BLE file.
    sendHeartbeat();

    if (!recording) {
        delay(1);
        return;
    }

    now = millis();

    // 1. Sample all sensors on the same schedule.
    if (now - lastSensorSampleMs >=
        SENSOR_SAMPLING_INTERVAL_MS) {

        lastSensorSampleMs = now;
        sampleAllSensors(now);
    }

    now = millis();

    // 2. Transmit according to its separate schedule.
    if (now - lastBLETransmissionMs >=
        BLE_TRANSMISSION_INTERVAL_MS) {

        lastBLETransmissionMs = now;
        transmitLatestReadings();
    }

    delay(1);
}
