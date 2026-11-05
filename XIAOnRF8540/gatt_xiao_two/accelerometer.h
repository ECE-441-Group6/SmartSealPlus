#ifndef ACCELEROMETER_H
#define ACCELEROMETER_H

#include <stdint.h>

// ADXL345 wiring (XIAO nRF52840 default I2C bus):
//   SDA -> D4
//   SCL -> D5

// ==================================================
// MOVEMENT TYPE CODES
//
// This number is sent in the BLE packet as "movement_type".
// To add a new movement type later, add a value here and
// make analyzeMovement() return it.
// ==================================================

enum MovementType : uint8_t {
    MOVEMENT_NONE    = 0,   // Stationary
    MOVEMENT_GENERAL = 1,   // Any movement above the threshold
    MOVEMENT_TILT    = 2,   // Reserved - not implemented yet
    MOVEMENT_TAP     = 3,   // Reserved - not implemented yet
    MOVEMENT_SHAKE   = 4    // Reserved - not implemented yet
};

// Initialize the ADXL345 (range + data rate). Call once in setup().
// Returns false if the sensor was not found.
bool accelerometerBegin();

// Read the sensor and calculate how much the acceleration
// changed since the previous reading.
void detectMovement();

// Decide what the calculated change means.
// Call right after detectMovement().
void analyzeMovement();

// Forget the previous reading and any pending movement.
// Call whenever sampling restarts after a pause.
void resetMovementDetection();

// Change the movement threshold (m/s^2) at runtime.
void setMovementThreshold(float threshold);

// Movement type to report in the next BLE packet (MovementType value).
// Holds the most significant movement seen since the last
// clearMovementCode(), so short movements between packets are not missed.
uint8_t getMovementCode();

// Start a new reporting window. Call after a packet was sent.
void clearMovementCode();

#endif