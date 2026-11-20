#pragma once

#include <Arduino.h>

// Initialize persistent anti-reuse state before advertising; provisioning is
// an explicit first-boot/recovery action, not an automatic counter reset.
bool initializeSequenceCounter(bool allowFirstBootProvisioning);
// Return the next unique 32-bit sequence, used as part of each CCM nonce.
bool getNextSequence(uint32_t &sequence);
