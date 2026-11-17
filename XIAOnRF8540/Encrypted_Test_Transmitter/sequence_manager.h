#pragma once

#include <Arduino.h>

bool initializeSequenceCounter(bool allowFirstBootProvisioning);
bool getNextSequence(uint32_t &sequence);
