#pragma once

#include <stdint.h>

// Copy to secrets.h and replace the example bytes with a dedicated test key
// and nonce prefix. Never reuse a production seal's key/prefix on this board.
constexpr uint8_t SEAL_ID = 2;
// Set to 1 only while provisioning blank sequence storage with a fresh key
// and nonce prefix. Set to 0 and upload again before normal use.
#define ALLOW_SEQUENCE_PROVISIONING 0
constexpr uint8_t AES_KEY[16] = {
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};
constexpr uint8_t NONCE_PREFIX[9] = {
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};
