
#include <Arduino.h>
#include <Adafruit_TinyUSB.h>
#include <bluefruit.h>
#include <Adafruit_nRFCrypto.h>
#include <nrf_cc310/include/crys_aesccm.h>

#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>

#include <math.h>
#include <stdint.h>
#include <string.h>

using namespace Adafruit_LittleFS_Namespace;

// =====================================================
// 1. SMARTSEAL CONFIGURATION
// =====================================================

#define TEMP_PIN A0
#define VIBRATION_PIN A2

constexpr uint8_t SEAL_ID = 1;

constexpr uint16_t MANUFACTURER_ID = 0x5353;

constexpr uint8_t MAGIC = 0xA5;
constexpr uint8_t PROTOCOL_VERSION = 2;

constexpr uint32_t ADVERTISEMENT_INTERVAL_MS = 5000;

constexpr uint16_t ADC_MAX = 4095;

constexpr float R25 = 10000.0f;
constexpr float BETA = 3950.0f;
constexpr float T25_K = 298.15f;

// Match this to the actual fixed resistor in your
// thermistor voltage-divider circuit.
// Your previous config.h specified 1000 ohms.
constexpr float R_BOTTOM_OHMS = 1000.0f;

// =====================================================
// 2. AES-128-CCM CONFIGURATION
// =====================================================

// TEST KEY ONLY.
// Must match the Python gateway key.
// Replace both copies before deployment.

const uint8_t AES_KEY[16] = {
    0x00, 0x11, 0x22, 0x33,
    0x44, 0x55, 0x66, 0x77,
    0x88, 0x99, 0xAA, 0xBB,
    0xCC, 0xDD, 0xEE, 0xFF
};

// TEST PREFIX ONLY.
// Must match the Python gateway prefix.

const uint8_t NONCE_PREFIX[9] = {
    0x10, 0x20, 0x30,
    0x40, 0x50, 0x60,
    0x70, 0x80, 0x90
};

constexpr uint8_t NONCE_LENGTH = 13;
constexpr uint8_t TAG_LENGTH = 8;

constexpr uint8_t HEADER_LENGTH = 7;
constexpr uint8_t PLAINTEXT_LENGTH = 5;
constexpr uint8_t PACKET_LENGTH = 20;

// =====================================================
// 3. PERSISTENT SEQUENCE COUNTER
// =====================================================

// Reserve 1024 sequence numbers at a time.
// This reduces internal flash writes.

constexpr uint32_t SEQUENCE_BLOCK_SIZE = 1024;

uint64_t nextSequence = 1;
uint32_t reservedEnd = 0;
int8_t activeSlot = -1;

bool sequenceStorageReady = false;

// =====================================================
// 4. SENSOR STATE
// =====================================================

float vibrationBaseline = 0.0f;

uint32_t lastAdvertisement = 0;

// =====================================================
// 5. LITTLEFS SEQUENCE STORAGE
// =====================================================

// Two independent records provide recovery if power
// is interrupted while updating the sequence counter.

uint32_t calculateChecksum(const uint8_t *data, size_t length) {

    uint32_t hash = 2166136261UL;

    for (size_t i = 0; i < length; i++) {
        hash ^= data[i];
        hash *= 16777619UL;
    }

    return hash;
}


void encodeUint32(uint8_t *destination, uint32_t value) {

    destination[0] = value & 0xFF;
    destination[1] = (value >> 8) & 0xFF;
    destination[2] = (value >> 16) & 0xFF;
    destination[3] = (value >> 24) & 0xFF;
}


uint32_t decodeUint32(const uint8_t *source) {

    return
        (uint32_t)source[0] |
        ((uint32_t)source[1] << 8) |
        ((uint32_t)source[2] << 16) |
        ((uint32_t)source[3] << 24);
}


const char *sequencePath(uint8_t slot) {

    return slot == 0 ? "/seq0.bin" : "/seq1.bin";
}


bool readSequenceSlot(uint8_t slot, uint32_t &highWater) {

    File file(InternalFS);

    if (!file.open(sequencePath(slot), FILE_O_READ)) {
        return false;
    }

    uint8_t record[12] = {0};

    uint32_t bytesRead = file.read(record, sizeof(record));

    file.close();

    if (bytesRead != sizeof(record)) {
        return false;
    }

    if (memcmp(record, "SSQ2", 4) != 0) {
        return false;
    }

    uint32_t storedChecksum = decodeUint32(record + 8);

    uint32_t calculatedChecksum =
        calculateChecksum(record, 8);

    if (storedChecksum != calculatedChecksum) {
        return false;
    }

    highWater = decodeUint32(record + 4);

    return true;
}


bool writeSequenceSlot(uint8_t slot, uint32_t highWater) {

    uint8_t record[12] = {0};

    memcpy(record, "SSQ2", 4);

    encodeUint32(record + 4, highWater);

    uint32_t checksum =
        calculateChecksum(record, 8);

    encodeUint32(record + 8, checksum);

    const char *path = sequencePath(slot);

    // Delete the older copy in this slot.
    // The other slot remains intact.

    if (InternalFS.exists(path)) {
        if (!InternalFS.remove(path)) {
            return false;
        }
    }

    File file(InternalFS);

    if (!file.open(path, FILE_O_WRITE)) {
        return false;
    }

    uint32_t bytesWritten =
        file.write(record, sizeof(record));

    file.close();

    if (bytesWritten != sizeof(record)) {
        return false;
    }

    // Read back and verify.
    uint32_t verifiedValue = 0;

    if (!readSequenceSlot(slot, verifiedValue)) {
        return false;
    }

    return verifiedValue == highWater;
}


bool reserveSequenceBlock() {

    if (reservedEnd == UINT32_MAX) {
        Serial.println("ERROR: Sequence counter exhausted.");
        return false;
    }

    uint64_t proposedEnd =
        (uint64_t)reservedEnd + SEQUENCE_BLOCK_SIZE;

    if (proposedEnd > UINT32_MAX) {
        proposedEnd = UINT32_MAX;
    }

    uint32_t newEnd = (uint32_t)proposedEnd;

    uint8_t targetSlot =
        activeSlot == 0 ? 1 : 0;

    if (!writeSequenceSlot(targetSlot, newEnd)) {
        Serial.println("ERROR: Could not save sequence counter.");
        return false;
    }

    reservedEnd = newEnd;
    activeSlot = targetSlot;

    Serial.print("Sequence range reserved through: ");
    Serial.println(reservedEnd);

    return true;
}


bool initializeSequenceCounter() {

    if (!InternalFS.begin()) {
        Serial.println("ERROR: Internal flash filesystem unavailable.");
        return false;
    }

    uint32_t highWater0 = 0;
    uint32_t highWater1 = 0;

    bool valid0 = readSequenceSlot(0, highWater0);
    bool valid1 = readSequenceSlot(1, highWater1);

    if (!valid0 && !valid1) {

        // If files exist but neither is valid, do not
        // silently restart at sequence zero.

        if (InternalFS.exists("/seq0.bin") ||
            InternalFS.exists("/seq1.bin")) {

            Serial.println("ERROR: Sequence records corrupted.");
            Serial.println("Re-provision with a NEW encryption key.");
            return false;
        }

        Serial.println("First boot: initializing sequence storage.");

        reservedEnd = 0;
        nextSequence = 1;
        activeSlot = -1;

    } else if (valid0 &&
               (!valid1 || highWater0 >= highWater1)) {

        reservedEnd = highWater0;
        activeSlot = 0;
        nextSequence = (uint64_t)reservedEnd + 1;

    } else {

        reservedEnd = highWater1;
        activeSlot = 1;
        nextSequence = (uint64_t)reservedEnd + 1;
    }

    // Reserve a fresh range BEFORE using any sequence number.
    // After a restart, unused numbers from the old range
    // are deliberately skipped.

    if (!reserveSequenceBlock()) {
        return false;
    }

    sequenceStorageReady = true;

    Serial.print("Next sequence: ");
    Serial.println((uint32_t)nextSequence);

    return true;
}


bool getNextSequence(uint32_t &sequence) {

    if (!sequenceStorageReady) {
        return false;
    }

    if (nextSequence > reservedEnd) {

        if (!reserveSequenceBlock()) {
            return false;
        }
    }

    if (nextSequence > UINT32_MAX) {
        Serial.println("ERROR: Sequence counter exhausted.");
        return false;
    }

    sequence = (uint32_t)nextSequence;

    nextSequence++;

    return true;
}

// =====================================================
// 6. SENSOR FUNCTIONS
// =====================================================

// Assumption:
// Thermistor connected to 3.3V.
// Fixed resistor connected from ADC to GND.

float readTemperatureC() {

    int raw = analogRead(TEMP_PIN);

    if (raw <= 0 || raw >= ADC_MAX) {
        return NAN;
    }

    float resistance =
        R_BOTTOM_OHMS *
        ((float)ADC_MAX / (float)raw - 1.0f);

    if (resistance <= 0.0f) {
        return NAN;
    }

    float inverseTemperature =
        (1.0f / T25_K) +
        (log(resistance / R25) / BETA);

    return (1.0f / inverseTemperature) - 273.15f;
}


void calibrateVibrationSensor() {

    Serial.println("Calibrating vibration baseline...");

    uint32_t total = 0;

    constexpr uint16_t SAMPLES = 1000;

    for (uint16_t i = 0; i < SAMPLES; i++) {

        total += analogRead(VIBRATION_PIN);

        delay(1);
    }

    vibrationBaseline =
        (float)total / SAMPLES;

    Serial.print("Vibration baseline: ");
    Serial.println(vibrationBaseline);
}


bool detectVibration() {

    constexpr uint16_t THRESHOLD = 100;
    constexpr uint8_t REQUIRED_HITS = 3;
    constexpr uint8_t TOTAL_SAMPLES = 20;

    uint8_t hits = 0;

    for (uint8_t i = 0; i < TOTAL_SAMPLES; i++) {

        int reading = analogRead(VIBRATION_PIN);

        float difference =
            fabs((float)reading - vibrationBaseline);

        if (difference > THRESHOLD) {
            hits++;
        }

        if (hits >= REQUIRED_HITS) {
            return true;
        }

        delay(1);
    }

    return false;
}

// =====================================================
// 7. AES-128-CCM ENCRYPTION
// =====================================================

bool encryptSensorData(
    const uint8_t *plaintext,
    const uint8_t *aad,
    const uint8_t *nonce,
    uint8_t *ciphertext,
    uint8_t *tag
) {

    CRYS_AESCCM_Key_t ccmKey = {0};

    // Copy the 128-bit key into CryptoCell's key buffer.
    memcpy(ccmKey, AES_KEY, sizeof(AES_KEY));

    CRYS_AESCCM_Mac_Res_t mac = {0};

    CRYSError_t result = CRYS_AESCCM(
        SASI_AES_ENCRYPT,
        ccmKey,
        CRYS_AES_Key128BitSize,
        (uint8_t *)nonce,
        NONCE_LENGTH,
        (uint8_t *)aad,
        HEADER_LENGTH,
        (uint8_t *)plaintext,
        PLAINTEXT_LENGTH,
        ciphertext,
        TAG_LENGTH,
        mac
    );

    if (result != CRYS_OK) {

        Serial.print("AES-CCM encryption error: ");
        Serial.println((uint32_t)result, HEX);

        return false;
    }

    memcpy(tag, mac, TAG_LENGTH);

    return true;
}

// =====================================================
// 8. BUILD ENCRYPTED BLE PACKET
// =====================================================

bool createEncryptedPacket(
    float temperatureC,
    bool vibrationDetected,
    uint8_t *packet
) {

    if (!isfinite(temperatureC) ||
        temperatureC < -3276.8f ||
        temperatureC > 3276.7f) {

        return false;
    }

    uint32_t sequence;

    if (!getNextSequence(sequence)) {
        return false;
    }

    // -------------------------------------------------
    // Build packet header
    // -------------------------------------------------

    packet[0] = MAGIC;
    packet[1] = PROTOCOL_VERSION;
    packet[2] = SEAL_ID;

    encodeUint32(packet + 3, sequence);

    // -------------------------------------------------
    // Build 13-byte nonce
    // -------------------------------------------------

    uint8_t nonce[NONCE_LENGTH];

    memcpy(nonce, NONCE_PREFIX, 9);

    // Use exactly the same sequence bytes as the
    // transmitted packet. Python uses payload[3:7].

    memcpy(nonce + 9, packet + 3, 4);

    // -------------------------------------------------
    // Build plaintext sensor data
    // -------------------------------------------------

    int16_t temperatureTenths =
        (int16_t)lroundf(temperatureC * 10.0f);

    uint16_t vibrationValue =
        vibrationDetected ? 100 : 0;

    uint8_t plaintext[PLAINTEXT_LENGTH];

    uint16_t temperatureRaw =
        (uint16_t)temperatureTenths;

    plaintext[0] = temperatureRaw & 0xFF;
    plaintext[1] = (temperatureRaw >> 8) & 0xFF;

    // Tamper is currently not connected to this sketch.
    plaintext[2] = 0;

    plaintext[3] = vibrationValue & 0xFF;
    plaintext[4] = (vibrationValue >> 8) & 0xFF;

    // -------------------------------------------------
    // Encrypt and authenticate
    // -------------------------------------------------

    uint8_t ciphertext[PLAINTEXT_LENGTH];

    uint8_t tag[TAG_LENGTH];

    // Header + sequence are authenticated as AAD.
    // They remain visible but cannot be modified
    // without authentication failure.

    if (!encryptSensorData(
            plaintext,
            packet,
            nonce,
            ciphertext,
            tag)) {

        return false;
    }

    // -------------------------------------------------
    // Assemble final packet
    // -------------------------------------------------

    memcpy(packet + 7, ciphertext, PLAINTEXT_LENGTH);

    memcpy(packet + 12, tag, TAG_LENGTH);

    return true;
}

// =====================================================
// 9. BLE ADVERTISING
// =====================================================

void startEncryptedAdvertising(const uint8_t *packet) {

    uint8_t manufacturerData[22];

    // Company ID, little-endian.
    manufacturerData[0] =
        MANUFACTURER_ID & 0xFF;

    manufacturerData[1] =
        MANUFACTURER_ID >> 8;

    memcpy(
        manufacturerData + 2,
        packet,
        PACKET_LENGTH
    );

    Bluefruit.Advertising.stop();

    Bluefruit.Advertising.clearData();

    Bluefruit.Advertising.addFlags(
        BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
    );

    Bluefruit.Advertising.addTxPower();

    Bluefruit.Advertising.addManufacturerData(
        manufacturerData,
        sizeof(manufacturerData)
    );

    Bluefruit.ScanResponse.clearData();

    Bluefruit.ScanResponse.addName();

    Bluefruit.Advertising.setInterval(32, 244);

    Bluefruit.Advertising.start(0);
}


// =====================================================
// 10. PUBLISH SENSOR DATA
// =====================================================

void publishSensorData() {

    float temperature = readTemperatureC();

    bool vibration = detectVibration();

    if (!isfinite(temperature)) {

        Serial.println("Invalid temperature reading.");
        return;
    }

    uint8_t encryptedPacket[PACKET_LENGTH];

    if (!createEncryptedPacket(
            temperature,
            vibration,
            encryptedPacket)) {

        Serial.println("Could not create encrypted packet.");
        return;
    }

    startEncryptedAdvertising(encryptedPacket);

    Serial.println();
    Serial.println("Encrypted BLE advertisement updated.");

    Serial.print("Temperature: ");
    Serial.println(temperature, 1);

    Serial.print("Vibration: ");
    Serial.println(vibration ? 1 : 0);

    Serial.print("Encrypted packet: ");

    for (uint8_t i = 0; i < PACKET_LENGTH; i++) {

        if (encryptedPacket[i] < 0x10) {
            Serial.print("0");
        }

        Serial.print(encryptedPacket[i], HEX);
        Serial.print(" ");
    }

    Serial.println();
}

// =====================================================
// 11. SETUP
// =====================================================

void setup() {

    Serial.begin(115200);

    delay(1000);

    Serial.println();
    Serial.println("==============================");
    Serial.println(" SmartSeal+ Secure BLE");
    Serial.println("==============================");

    analogReadResolution(12);

    pinMode(TEMP_PIN, INPUT);
    pinMode(VIBRATION_PIN, INPUT);

    // Initialize Nordic CryptoCell.
    if (!nRFCrypto.begin()) {

        Serial.println("ERROR: CryptoCell initialization failed.");

        while (true) {
            delay(1000);
        }
    }

    Serial.println("CryptoCell initialized.");

    // Initialize persistent sequence storage.
    if (!initializeSequenceCounter()) {

        Serial.println("ERROR: Secure sequence initialization failed.");

        while (true) {
            delay(1000);
        }
    }

    // Initialize BLE.
    Bluefruit.begin();

    Bluefruit.setName("SmartSeal-XIAO");

    Serial.println("BLE initialized.");

    // Calibrate vibration sensor.
    calibrateVibrationSensor();

    // Start first encrypted advertisement.
    publishSensorData();

    lastAdvertisement = millis();

    Serial.println("SmartSeal secure advertising is running.");
}


// =====================================================
// 12. MAIN LOOP
// =====================================================

void loop() {

    if (millis() - lastAdvertisement >=
        ADVERTISEMENT_INTERVAL_MS) {

        lastAdvertisement = millis();

        publishSensorData();
    }

    delay(10);
}