#pragma once

#include <Arduino.h>

#include "secrets.h"

// Analog/digital inputs used by the production SmartSeal board.
#define TEMP_PIN A0
#define VIBRATION_PIN A2
#define RECORD_BUTTON_PIN D6
#define BUZZER_PIN D3

constexpr uint16_t MANUFACTURER_ID = 0x5353;
// Wire protocol identifiers; these must match Gateway/ble_scanner.py.
constexpr uint8_t MAGIC = 0xA5;
constexpr uint8_t PROTOCOL_VERSION = 5;
// Vibration magnitude is encoded in whole millivolts in protocol version 5.
// Sensor readings are encrypted and broadcast every five seconds while armed.
constexpr uint32_t ADVERTISEMENT_INTERVAL_MS = 5000;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 40;
constexpr uint16_t ADC_MAX = 4095;
constexpr float ADC_REFERENCE_VOLTAGE = 3.05f;
constexpr float R25 = 10000.0f;
constexpr float BETA = 3950.0f;
constexpr float T25_K = 298.15f;
constexpr float R_BOTTOM_OHMS = 1000.0f;
constexpr uint8_t NONCE_LENGTH = 13;
constexpr uint8_t TAG_LENGTH = 8;
// The first 7 bytes are authenticated header/AAD; 6 sensor bytes are encrypted.
constexpr uint8_t HEADER_LENGTH = 7;
constexpr uint8_t PLAINTEXT_LENGTH = 6;
// The 21-byte packet plus the 2-byte BLE company ID fits in legacy advertising.
constexpr uint8_t PACKET_LENGTH = 21;
