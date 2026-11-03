#pragma once

#include <stdint.h>

// SmartSeal+ HMAC-SHA256 key configuration template.
//
// Copy this file to device_secrets.h before compiling.
//
// WARNING:
// The key below is for development/testing ONLY.
// It must never be used to secure deployed SmartSeal+ devices.
//
// For production, generate a unique, cryptographically random
// 32-byte key for each SmartSeal device.
// Configure the gateway with the matching key.

static const uint8_t SMARTSEAL_HMAC_KEY[32] = {
    0xA1, 0xA1, 0xA1, 0xA1,
    0xA1, 0xA1, 0xA1, 0xA1,
    0xA1, 0xA1, 0xA1, 0xA1,
    0xA1, 0xA1, 0xA1, 0xA1,
    0xA1, 0xA1, 0xA1, 0xA1,
    0xA1, 0xA1, 0xA1, 0xA1,
    0xA1, 0xA1, 0xA1, 0xA1,
    0xA1, 0xA1, 0xA1, 0xA1
};
