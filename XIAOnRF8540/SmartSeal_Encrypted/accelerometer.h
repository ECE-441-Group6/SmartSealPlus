#pragma once

#include <stdint.h>

enum MovementType : uint8_t {
    MOVEMENT_NONE = 0,
    MOVEMENT_GENERAL = 1,
    MOVEMENT_TILT = 2,
    MOVEMENT_TAP = 3,
    MOVEMENT_SHAKE = 4
};

bool accelerometerBegin();
void resetMovementDetection();
void detectMovement();
uint8_t getMovementCode();
void clearMovementCode();
