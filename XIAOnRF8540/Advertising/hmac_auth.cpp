#include "hmac_auth.h"

#include <Arduino.h>
#include <Adafruit_nRFCrypto.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static bool calculateSha256(
    const uint8_t* data,
    size_t length,
    uint8_t digest[32]
) {
    if (data == nullptr || digest == nullptr) {
        return false;
    }

    nRFCrypto_Hash hash;

    if (!hash.begin(CRYS_HASH_SHA256_mode)) {
        return false;
    }

    if (!hash.update(const_cast<uint8_t*>(data), length)) {
        return false;
    }

    uint8_t result[64] = {0};
    const uint8_t digestLength = hash.end(result);

    if (digestLength != 32) {
        return false;
    }

    memcpy(digest, result, 32);
    return true;
}

bool generatePacketHmac(
    const uint8_t* message,
    size_t messageLength,
    const uint8_t* key,
    size_t keyLength,
    char output[65]
) {
    if (message == nullptr || key == nullptr ||
        output == nullptr || keyLength == 0) {
        return false;
    }

    if (!nRFCrypto.begin()) {
        return false;
    }

    uint8_t keyBlock[64] = {0};
    uint8_t innerPad[64];
    uint8_t outerPad[64];
    uint8_t innerDigest[32];
    uint8_t finalDigest[32];

    bool success = false;

    do {
        if (keyLength > 64) {
            if (!calculateSha256(key, keyLength, keyBlock)) {
                break;
            }
        } else {
            memcpy(keyBlock, key, keyLength);
        }

        for (size_t i = 0; i < 64; ++i) {
            innerPad[i] = keyBlock[i] ^ 0x36;
            outerPad[i] = keyBlock[i] ^ 0x5c;
        }

        nRFCrypto_Hash innerHash;

        if (!innerHash.begin(CRYS_HASH_SHA256_mode)) {
            break;
        }

        if (!innerHash.update(innerPad, sizeof(innerPad)) ||
            !innerHash.update(
                const_cast<uint8_t*>(message),
                messageLength)) {
            break;
        }

        uint8_t innerResult[64] = {0};

        if (innerHash.end(innerResult) != 32) {
            break;
        }

        memcpy(innerDigest, innerResult, 32);

        nRFCrypto_Hash outerHash;

        if (!outerHash.begin(CRYS_HASH_SHA256_mode)) {
            break;
        }

        if (!outerHash.update(outerPad, sizeof(outerPad)) ||
            !outerHash.update(innerDigest, sizeof(innerDigest))) {
            break;
        }

        uint8_t outerResult[64] = {0};

        if (outerHash.end(outerResult) != 32) {
            break;
        }

        memcpy(finalDigest, outerResult, 32);

        const char hex[] = "0123456789abcdef";

        for (size_t i = 0; i < 32; ++i) {
            output[i * 2] = hex[finalDigest[i] >> 4];
            output[i * 2 + 1] = hex[finalDigest[i] & 0x0F];
        }

        output[64] = '\0';
        success = true;

    } while (false);

    nRFCrypto.end();

    return success;
}

bool formatAuthenticationMessage(
    uint32_t sealId,
    uint32_t eventSequence,
    float temperature,
    bool tamper,
    float vibration,
    char* output,
    size_t outputSize
) {
    if (output == nullptr || outputSize == 0 ||
        sealId == 0 ||
        !isfinite(temperature) ||
        !isfinite(vibration) ||
        vibration < 0.0f) {
        return false;
    }

    const int written = snprintf(
        output,
        outputSize,
        "seal_id=%lu\n"
        "event_sequence=%lu\n"
        "temperature=%.2f\n"
        "tamper=%s\n"
        "vibration=%.3f",
        static_cast<unsigned long>(sealId),
        static_cast<unsigned long>(eventSequence),
        static_cast<double>(temperature),
        tamper ? "true" : "false",
        static_cast<double>(vibration)
    );

    return written > 0 &&
           static_cast<size_t>(written) < outputSize;
}
