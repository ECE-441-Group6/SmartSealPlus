#include "accelerometer.h"

#include <Arduino.h>
#include <Wire.h>
#include <math.h>

namespace {
constexpr uint8_t ADXL345_ADDRESS = 0x53;
constexpr uint8_t REG_DATA_FORMAT = 0x31;
constexpr uint8_t REG_BW_RATE = 0x2C;
constexpr uint8_t REG_POWER_CTL = 0x2D;
constexpr uint8_t REG_DATA_X0 = 0x32;
constexpr uint8_t MEASURE_MODE = 0x08;
constexpr uint8_t FULL_RESOLUTION_16G = 0x0B;
constexpr uint8_t DATA_RATE_100_HZ = 0x0A;
constexpr float ADXL345_SCALE_MPS2 = 0.0039f * 9.80665f;
constexpr float MOVEMENT_THRESHOLD = 1.5f;
constexpr uint8_t REQUIRED_MOVEMENT_SAMPLES = 4;

bool sensorReady = false;
bool firstReading = true;
float previousX = 0.0f;
float previousY = 0.0f;
float previousZ = 0.0f;
uint8_t latchedMovement = MOVEMENT_NONE;
uint8_t movementSamples = 0;

bool writeRegister(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(ADXL345_ADDRESS);
    Wire.write(reg);
    Wire.write(value);
    return Wire.endTransmission() == 0;
}

bool readAcceleration(float &x, float &y, float &z) {
    Wire.beginTransmission(ADXL345_ADDRESS);
    Wire.write(REG_DATA_X0);
    if (Wire.endTransmission(false) != 0 ||
        Wire.requestFrom(ADXL345_ADDRESS, (uint8_t)6) != 6) {
        return false;
    }

    const int16_t rawX = (int16_t)(Wire.read() | (Wire.read() << 8));
    const int16_t rawY = (int16_t)(Wire.read() | (Wire.read() << 8));
    const int16_t rawZ = (int16_t)(Wire.read() | (Wire.read() << 8));

    x = rawX * ADXL345_SCALE_MPS2;
    y = rawY * ADXL345_SCALE_MPS2;
    z = rawZ * ADXL345_SCALE_MPS2;
    return isfinite(x) && isfinite(y) && isfinite(z);
}
}

bool accelerometerBegin() {
    Wire.begin();

    Wire.beginTransmission(ADXL345_ADDRESS);
    Wire.write(0x00);
    if (Wire.endTransmission(false) != 0 ||
        Wire.requestFrom(ADXL345_ADDRESS, (uint8_t)1) != 1 ||
        Wire.read() != 0xE5) {
        Serial.println("ADXL345 not detected; movement detection disabled.");
        return false;
    }

    if (!writeRegister(REG_DATA_FORMAT, FULL_RESOLUTION_16G) ||
        !writeRegister(REG_BW_RATE, DATA_RATE_100_HZ) ||
        !writeRegister(REG_POWER_CTL, MEASURE_MODE)) {
        Serial.println(
            "ADXL345 configuration failed; movement detection disabled."
        );
        return false;
    }

    sensorReady = true;
    resetMovementDetection();
    Serial.println("ADXL345 initialized.");
    return true;
}

void resetMovementDetection() {
    firstReading = true;
    latchedMovement = MOVEMENT_NONE;
    movementSamples = 0;
}

void detectMovement() {
    if (!sensorReady) {
        return;
    }

    float currentX;
    float currentY;
    float currentZ;
    if (!readAcceleration(currentX, currentY, currentZ)) {
        return;
    }

    if (firstReading) {
        previousX = currentX;
        previousY = currentY;
        previousZ = currentZ;
        firstReading = false;
        return;
    }

    const float deltaX = currentX - previousX;
    const float deltaY = currentY - previousY;
    const float deltaZ = currentZ - previousZ;

    previousX = currentX;
    previousY = currentY;
    previousZ = currentZ;

    const float deltaMagnitude = sqrtf(
        deltaX * deltaX +
        deltaY * deltaY +
        deltaZ * deltaZ
    );

    if (deltaMagnitude > MOVEMENT_THRESHOLD) {
        if (movementSamples < REQUIRED_MOVEMENT_SAMPLES) {
            movementSamples++;
        }
    } else {
        movementSamples = 0;
    }

    if (movementSamples >= REQUIRED_MOVEMENT_SAMPLES) {
        latchedMovement = MOVEMENT_GENERAL;
    }
}

uint8_t getMovementCode() {
    return latchedMovement;
}

void clearMovementCode() {
    latchedMovement = MOVEMENT_NONE;
    movementSamples = 0;
}
