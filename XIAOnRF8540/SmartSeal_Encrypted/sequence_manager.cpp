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
        (uint32_t)source[0] |         //LSB 
        ((uint32_t)source[1] << 8) |
        ((uint32_t)source[2] << 16) |
        ((uint32_t)source[3] << 24);   //MSB
}


const char *sequencePath(uint8_t slot) {
    return slot == 0 ? "/seq0.bin" : "/seq1.bin";
}


bool readSequenceSlot(uint8_t slot, uint32_t &highWater, bool &mirroredRecord) {
    //Create file object for the internal flash filesystem.
    File file(InternalFS);   //typeName, ObjectName()


    // Open the file in read mode, and copy into the record buffer.
    if (!file.open(sequencePath(slot), FILE_O_READ)) { //.open(path, mode)
        Serial.println("ERROR: Could not open sequence slot " + String(slot) + ".");
        return false;
    }
    uint8_t record[12] = {0};
    uint32_t bytesRead = file.read(record, sizeof(record)); //.read(buffer, length) returns number of bytes it stored
    file.close();


    //check read looks correct
    if (bytesRead != sizeof(record)) {
        Serial.println("ERROR: Incomplete read from sequence slot " + String(slot) + ".");
        return false;
    }
    const bool isMirroredRecord = memcmp(record, "SSQ3", 4) == 0;
    if (!isMirroredRecord && memcmp(record, "SSQ2", 4) != 0) {
        Serial.println("ERROR: First bytes of sequence slot " + String(slot) + " do not match expected signature.");
        return false;
    }

    //verify checksum to validate record data has not been corrupted.
    uint32_t storedChecksum = decodeUint32(record + 8); //Pass point to the 9th byte
    uint32_t calculatedChecksum = calculateChecksum(record, 8); //Calculate checksum based on first 8 bytes
    if (storedChecksum != calculatedChecksum) {
        Serial.println("ERROR: Checksum mismatch in sequence slot " + String(slot) + ".");
        return false;
    }

    highWater = decodeUint32(record + 4); //highwater0 or 1 depending on slot passed in.
    mirroredRecord = isMirroredRecord;
    return true;
}


bool writeSequenceSlot(uint8_t slot, uint32_t highWater) {

    uint8_t record[12] = {0};

    memcpy(record, "SSQ3", 4);

    encodeUint32(record + 4, highWater);

    uint32_t checksum = calculateChecksum(record, 8);

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
    bool verifiedMirroredRecord = false;

    if (!readSequenceSlot(slot, verifiedValue, verifiedMirroredRecord)) {
        return false;
    }

    return verifiedValue == highWater && verifiedMirroredRecord;
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

    // Store the same high-water mark in both slots before using any value in
    // the new range. A single missing slot then cannot roll the counter back.
    if (!writeSequenceSlot(0, newEnd) ||
        !writeSequenceSlot(1, newEnd)) {
        Serial.println("ERROR: Could not save sequence counter.");
        return false;
    }

    reservedEnd = newEnd;
    activeSlot = 0;

    Serial.print("Sequence range reserved through: ");
    Serial.println(reservedEnd);

    return true;
}
}


bool initializeSequenceCounter(bool allowFirstBootProvisioning) {
    // Initialize the internal flash filesystem. to store sequence numbers after shutdown.
    while(!InternalFS.begin()) { 
        Serial.println("ERROR: Failed to initialize internal flash filesystem. Retrying...");
        delay(1000);
    }

    const bool slot0Exists = InternalFS.exists("/seq0.bin");
    const bool slot1Exists = InternalFS.exists("/seq1.bin");

    //variables that hold the highest reserved sequence number for each slot
    uint32_t highWater0 = 0;
    uint32_t highWater1 = 0;
    bool mirrored0 = false;
    bool mirrored1 = false;

    //variables that hold if sequences are valid for each slot
    bool valid0 = readSequenceSlot(0, highWater0, mirrored0);
    bool valid1 = readSequenceSlot(1, highWater1, mirrored1);

    bool invalidSequenceState =
        (slot0Exists && !valid0) || (slot1Exists && !valid1);
    if (!invalidSequenceState && (valid0 || valid1)) {
        const uint8_t newestSlot =
            valid0 && (!valid1 || highWater0 >= highWater1) ? 0 : 1;
        const uint32_t newestHighWater = newestSlot == 0 ? highWater0 : highWater1;
        const bool newestIsMirrored = newestSlot == 0 ? mirrored0 : mirrored1;
        const uint64_t reservedBlocks =
            ((uint64_t)newestHighWater + SEQUENCE_BLOCK_SIZE - 1) /
            SEQUENCE_BLOCK_SIZE;
        const uint8_t expectedLegacySlot =
            (reservedBlocks & 1) ? 0 : 1;
        if (!newestIsMirrored && newestSlot != expectedLegacySlot) {
            Serial.println(
                "ERROR: Legacy sequence state may have rolled back."
            );
            invalidSequenceState = true;
        }
    }

    if (invalidSequenceState && !allowFirstBootProvisioning) {
        Serial.println("ERROR: A sequence record exists but is invalid.");
        Serial.println(
            "Install a NEW encryption key and nonce prefix, then provision."
        );
        return false;
    }
    if (invalidSequenceState) {
        // Explicit provisioning discards both records; the operator must
        // install a new key/prefix before allowing the counter to restart.
        valid0 = false;
        valid1 = false;
    }

    if (!valid0 && !valid1) {
        const bool sequenceFilesExist = slot0Exists || slot1Exists;

        // Missing or corrupt sequence storage must never silently restart
        // under the old key. Provisioning requires an explicit boot-time
        // button press and a newly provisioned key.
        if (!allowFirstBootProvisioning) {
            Serial.println(
                sequenceFilesExist
                    ? "ERROR: Sequence records corrupted."
                    : "ERROR: Sequence storage is missing."
            );
            Serial.println(
                "Provision with a NEW encryption key and hold D6 during boot."
            );
            return false;
        }

        if (sequenceFilesExist) {
            Serial.println(
                "Sequence storage is corrupt; explicit provisioning requested."
            );
            Serial.println("Ensure a NEW encryption key is installed.");
            for (uint8_t slot = 0; slot < 2; slot++) {
                const char *path = sequencePath(slot);
                if (InternalFS.exists(path) && !InternalFS.remove(path)) {
                    Serial.println("ERROR: Could not remove a corrupt sequence record.");
                    return false;
                }
            }
        } else {
            Serial.println("First boot: initializing sequence storage.");
        }

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
