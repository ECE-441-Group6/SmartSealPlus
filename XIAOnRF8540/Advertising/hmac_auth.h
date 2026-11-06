#pragma once

#include <stddef.h>
#include <stdint.h>

// Generate a lowercase hexadecimal HMAC-SHA256 tag.
// output must contain at least 65 bytes.
bool generatePacketHmac(
    const uint8_t* message,
    size_t messageLength,
    const uint8_t* key,
    size_t keyLength,
    char output[65]
);

// Construct the authentication message shared with the Python gateway.
// Returns false if the output buffer is too small or values are invalid.
bool formatAuthenticationMessage(
    uint32_t sealId,
    uint32_t eventSequence,
    float temperature,
    bool tamper,
    float vibration,
    char* output,
    size_t outputSize
);
