#pragma once

#include <Arduino.h>

bool initializeSequenceCounter();
bool getNextSequence(uint32_t &sequence);
