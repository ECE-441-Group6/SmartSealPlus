#include "sequence_manager.h"

#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include <stdint.h>
#include <string.h>

using namespace Adafruit_LittleFS_Namespace;

namespace {
constexpr uint32_t SEQUENCE_BLOCK_SIZE = 1024;

uint64_t nextSequence = 1;
uint32_t reservedEnd = 0;
int8_t activeSlot = -1;
bool sequenceStorageReady = false;
}

namespace {
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
