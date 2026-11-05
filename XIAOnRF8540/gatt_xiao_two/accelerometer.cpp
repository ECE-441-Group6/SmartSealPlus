// ==================================================
// accelerometer.cpp
//
// Basic movement detection using an ADXL345 and the
// Adafruit ADXL345 Unified library.
//
// How main.cpp uses this module:
//
//   accelerometerBegin()    once, in setup()
//   detectMovement()        repeatedly: reads the sensor and
//                           calculates how much the acceleration
//                           changed since the previous reading
//   analyzeMovement()       right after detectMovement(): decides
//                           what that change means
//   getMovementCode()       when building the BLE packet
//   clearMovementCode()     after the packet was sent
//
// Wiring (XIAO nRF52840 default I2C bus): SDA = D4, SCL = D5
// ==================================================

#include <Arduino.h>
#include <math.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_ADXL345_U.h>

#include "accelerometer.h"


// ==================================================
// FUNCTION PROTOTYPES
//
// Listed here because this is a .cpp file, not an .ino
// (the Arduino IDE only generates prototypes for .ino
// files). The public functions are also declared in
// accelerometer.h.
// ==================================================

bool accelerometerBegin();
void detectMovement();
void analyzeMovement();
void resetMovementDetection();
void setMovementThreshold(float threshold);
uint8_t getMovementCode();
void clearMovementCode();

static void latchMovementCode(uint8_t code);


// ==================================================
// CONFIGURATION
// ==================================================

// Movement threshold in m/s^2.
// If the acceleration changes by MORE than this between two
// consecutive readings, the board is considered to be moving.
// 0.5 m/s^2 (about 0.05 g) is only a starting point: watch the
// Delta values printed to the Serial Monitor. At rest they should
// stay clearly below the threshold, and during the movement you
// care about they should clearly exceed it.
static float movementThreshold = 0.5f;

// true  = print a line for every analyzed reading (useful while
//         tuning the threshold)
// false = print only when the state changes between
//         MOVEMENT DETECTED and STATIONARY
static bool printEveryReading = true;


// ==================================================
// SENSOR OBJECT
// ==================================================

static Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);


// ==================================================
// SHARED VARIABLES
//
// File-level globals so that detectMovement(), analyzeMovement()
// and the future classification code can share readings and results.
// ==================================================

// Most recent reading in m/s^2 (a board lying flat reads Z = ~9.8).
// Kept global because future classifiers will need the raw values,
// for example tilt depends on the orientation of X/Y/Z.
static float currentX = 0.0f;
static float currentY = 0.0f;
static float currentZ = 0.0f;

// Reading from the previous call to detectMovement().
static float previousX = 0.0f;
static float previousY = 0.0f;
static float previousZ = 0.0f;

// Output of detectMovement() and input of analyzeMovement():
// the size of the change between the two readings, in m/s^2.
static float deltaMagnitude = 0.0f;

// true when detectMovement() produced a delta that analyzeMovement()
// has not looked at yet. Keeps the same delta from being analyzed twice.
static bool newDeltaAvailable = false;

// Output of analyzeMovement().
static bool movementDetected = false;          // delta above threshold?
static uint8_t movementCode = MOVEMENT_NONE;   // type for the latest reading

// The code that goes out in the next BLE packet. It is "latched":
// it holds the most significant movement seen since the last
// clearMovementCode(), because analysis runs far more often than
// packets are sent.
static uint8_t latchedMovementCode = MOVEMENT_NONE;

// State flags.
static bool accelReady = false;            // ADXL345 found and configured
static bool firstReading = true;           // next reading only sets the baseline
static bool lastPrintedDetected = false;   // used for print-on-change mode


// ==================================================
// INITIALIZATION
// Configure the ADXL345. Called once from setup().
// ==================================================

bool accelerometerBegin() {

  if (!accel.begin()) {

    // Do not hang here: the rest of the system (BLE, other sensors)
    // should keep running. The movement code simply stays at 0.
    Serial.println("ADXL345 not detected - movement detection disabled.");

    accelReady = false;
    return false;
  }

  // Measurement range: +/-16 g leaves headroom for hard taps and
  // shakes later.
  accel.setRange(ADXL345_RANGE_16_G);

  // Output data rate: the sensor produces 100 new samples per second,
  // so each reading is at most 10 ms old (main.cpp reads it less often).
  accel.setDataRate(ADXL345_DATARATE_100_HZ);

  accelReady = true;

  resetMovementDetection();

  Serial.println("ADXL345 initialized.");

  return true;
}


// ==================================================
// RESET
// Forget the previous reading and any pending result.
//
// Call this whenever sampling restarts after a pause. Otherwise the
// first new reading would be compared with an old one, and a board
// that was moved in the meantime would look like movement.
// ==================================================

void resetMovementDetection() {

  firstReading = true;
  newDeltaAvailable = false;

  deltaMagnitude = 0.0f;
  movementDetected = false;
  movementCode = MOVEMENT_NONE;
  latchedMovementCode = MOVEMENT_NONE;

  lastPrintedDetected = false;
}


// ==================================================
// MOVEMENT DETECTION
// Read the sensor and calculate the acceleration change.
// This function only measures. It does not decide anything.
// ==================================================

void detectMovement() {

  if (!accelReady) {
    return;
  }

  // Get one new reading. The library returns m/s^2.
  sensors_event_t event;
  accel.getEvent(&event);

  float x = event.acceleration.x;
  float y = event.acceleration.y;
  float z = event.acceleration.z;

  // Ignore an invalid reading instead of treating it as movement.
  if (!isfinite(x) || !isfinite(y) || !isfinite(z)) {
    return;
  }

  currentX = x;
  currentY = y;
  currentZ = z;

  // First valid reading: there is nothing to compare it with yet, so
  // just store it as the baseline. This prevents a false detection
  // at startup (comparing against the initial zeros).
  if (firstReading) {

    previousX = currentX;
    previousY = currentY;
    previousZ = currentZ;

    firstReading = false;
    newDeltaAvailable = false;

    return;
  }

  // Change on each axis since the previous reading.
  float deltaX = currentX - previousX;
  float deltaY = currentY - previousY;
  float deltaZ = currentZ - previousZ;

  // Combined change (3-D magnitude of the difference):
  //
  //   dA = sqrt(dX^2 + dY^2 + dZ^2)
  //
  // Combining the axes means movement in any direction counts
  // equally. Gravity cancels out as long as the board holds still,
  // so a stationary board gives a delta close to zero in any
  // orientation.
  deltaMagnitude = sqrtf(
    deltaX * deltaX +
    deltaY * deltaY +
    deltaZ * deltaZ
  );

  // The current reading becomes the previous one for the next call.
  previousX = currentX;
  previousY = currentY;
  previousZ = currentZ;

  // Tell analyzeMovement() that a new result is ready.
  newDeltaAvailable = true;
}


// ==================================================
// MOVEMENT ANALYSIS
// Decide what the calculated change means.
// This function never touches the sensor.
// ==================================================

void analyzeMovement() {

  // Nothing to analyze until detectMovement() has produced a delta.
  // (The very first reading only sets the baseline, so no delta exists.)
  if (!newDeltaAvailable) {
    return;
  }

  newDeltaAvailable = false;   // use each delta only once

  // ---- Step 1: basic movement detection ----
  // Did the acceleration change by more than the threshold?
  movementDetected = (deltaMagnitude > movementThreshold);

  // ---- Step 2: decide which movement type to report ----
  // Today there are only two outcomes: stationary or general movement.
  uint8_t code = MOVEMENT_NONE;

  if (movementDetected) {
    code = MOVEMENT_GENERAL;
  }

  // ----------------------------------------------------------
  // FUTURE: movement classification goes here.
  //
  // Each classifier can inspect the shared globals (currentX/Y/Z,
  // previousX/Y/Z, deltaMagnitude) and replace 'code' with a more
  // specific type, for example:
  //
  //   if (isTilt())   code = MOVEMENT_TILT;
  //   if (isTap())    code = MOVEMENT_TAP;
  //   if (isShake())  code = MOVEMENT_SHAKE;
  //
  // Note: this delta only reacts to CHANGES between readings. A
  // slow, smooth tilt changes very little per reading, so a tilt
  // classifier will probably need to compare the current orientation
  // against a longer-term baseline instead.
  // ----------------------------------------------------------

  movementCode = code;

  // Remember it until the next BLE packet goes out.
  latchMovementCode(code);

  // ---- Step 3: print the result ----
  bool stateChanged = (movementDetected != lastPrintedDetected);

  if (printEveryReading || stateChanged) {

    if (movementDetected) {
      Serial.print("MOVEMENT DETECTED");
    } else {
      Serial.print("STATIONARY");
    }

    Serial.print(" | Delta: ");
    Serial.print(deltaMagnitude, 3);
    Serial.print(" | Type: ");
    Serial.println(movementCode);
  }

  lastPrintedDetected = movementDetected;
}


// ==================================================
// RESULT ACCESS (used by main.cpp for the BLE packet)
// ==================================================

// Keep the most significant code seen since the last clear.
// Higher code wins, so a specific type (tilt, tap, shake) outranks
// general movement. Change this rule if you want a different priority.
static void latchMovementCode(uint8_t code) {

  if (code > latchedMovementCode) {
    latchedMovementCode = code;
  }
}

uint8_t getMovementCode() {
  return latchedMovementCode;
}

// Clear only after the packet was actually sent, so a movement is not
// lost if the BLE notification fails (for example, no connection).
void clearMovementCode() {
  latchedMovementCode = MOVEMENT_NONE;
}

void setMovementThreshold(float threshold) {

  if (isfinite(threshold) && threshold >= 0.0f) {
    movementThreshold = threshold;
  }
}