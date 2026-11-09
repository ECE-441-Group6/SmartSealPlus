#pragma once

#include <Arduino.h>

#include "secrets.h"

#define TEMP_PIN A0
#define VIBRATION_PIN A2
#define RECORD_BUTTON_PIN D6

constexpr uint16_t MANUFACTURER_ID = 0x5353;
constexpr uint8_t MAGIC = 0xA5;
constexpr uint8_t PROTOCOL_VERSION = 3;
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
constexpr uint8_t HEADER_LENGTH = 7;
constexpr uint8_t PLAINTEXT_LENGTH = 6;
constexpr uint8_t PACKET_LENGTH = 21;
