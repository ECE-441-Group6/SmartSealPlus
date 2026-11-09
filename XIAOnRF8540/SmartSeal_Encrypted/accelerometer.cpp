#include "accelerometer.h"

#include <Adafruit_ADXL345_U.h>
#include <Adafruit_Sensor.h>
#include <Arduino.h>
#include <Wire.h>
#include <math.h>

namespace {
Adafruit_ADXL345_Unified accelerometer(12345);
constexpr float MOVEMENT_THRESHOLD = 0.5f;
bool sensorReady = false;
bool firstReading = true;
float previousX = 0.0f;
float previousY = 0.0f;
float previousZ = 0.0f;
uint8_t latchedMovement = MOVEMENT_NONE;
}

bool accelerometerBegin() {
    if (!accelerometer.begin()) {
        Serial.println("ADXL345 not detected; movement detection disabled.");
        return false;
    }

    accelerometer.setRange(ADXL345_RANGE_16_G);
    accelerometer.setDataRate(ADXL345_DATARATE_100_HZ);
    sensorReady = true;
    resetMovementDetection();
    Serial.println("ADXL345 initialized.");
    return true;
}

void resetMovementDetection() {
    firstReading = true;
    latchedMovement = MOVEMENT_NONE;
}

void detectMovement() {
    if (!sensorReady) {
        return;
    }

    sensors_event_t event;
    accelerometer.getEvent(&event);
    if (!isfinite(event.acceleration.x) ||
        !isfinite(event.acceleration.y) ||
        !isfinite(event.acceleration.z)) {
        return;
    }

    if (firstReading) {
        previousX = event.acceleration.x;
        previousY = event.acceleration.y;
        previousZ = event.acceleration.z;
        firstReading = false;
        return;
    }

    const float deltaX = event.acceleration.x - previousX;
    const float deltaY = event.acceleration.y - previousY;
    const float deltaZ = event.acceleration.z - previousZ;

    previousX = event.acceleration.x;
    previousY = event.acceleration.y;
    previousZ = event.acceleration.z;

    if (sqrtf(deltaX * deltaX + deltaY * deltaY + deltaZ * deltaZ)
        > MOVEMENT_THRESHOLD) {
        latchedMovement = MOVEMENT_GENERAL;
    }
}

uint8_t getMovementCode() {
    return latchedMovement;
}

void clearMovementCode() {
    latchedMovement = MOVEMENT_NONE;
}
