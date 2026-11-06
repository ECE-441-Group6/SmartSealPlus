#include "sequence_storage.h"

#include <Arduino.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include <stdint.h>
#include <stdio.h>

using namespace Adafruit_LittleFS_Namespace;

namespace {

constexpr uint32_t RESERVATION_SIZE = 1000;
constexpr uint32_t RECORD_MAGIC = 0x53535131;
constexpr uint32_t MAX_SEQUENCE = UINT32_MAX;

const char* const RECORD_PATH = "/sequence.dat";
const char* const TEMP_PATH = "/sequence.tmp";

struct SequenceRecord {
  uint32_t magic;
  uint32_t reservedUntil;
  uint32_t checksum;
};

uint32_t nextSequence = 0;
uint32_t reservationEnd = 0;
bool storageReady = false;

uint32_t checksumFor(uint32_t reservedUntil) {
  return RECORD_MAGIC ^ reservedUntil ^ 0xA5A55A5A;
}

bool readRecord(SequenceRecord* record) {
  if (record == nullptr) {
    return false;
  }

  File file(InternalFS);
  if (!file.open(RECORD_PATH, FILE_O_READ)) {
    return false;
  }

  const bool validSize = file.size() == sizeof(SequenceRecord);
  const int bytesRead = validSize
      ? file.read(record, sizeof(SequenceRecord))
      : -1;

  file.close();

  return validSize &&
         bytesRead == static_cast<int>(sizeof(SequenceRecord)) &&
         record->magic == RECORD_MAGIC &&
         record->checksum == checksumFor(record->reservedUntil);
}

bool saveReservation(uint32_t newEnd) {
  SequenceRecord record = {
      RECORD_MAGIC,
      newEnd,
      checksumFor(newEnd)
  };

  if (InternalFS.exists(TEMP_PATH) && !InternalFS.remove(TEMP_PATH)) {
    return false;
  }

  File file(InternalFS);
  if (!file.open(TEMP_PATH, FILE_O_WRITE)) {
    return false;
  }

  const size_t written = file.write(
      reinterpret_cast<const uint8_t*>(&record),
      sizeof(record)
  );

  file.flush();
  file.close();

  if (written != sizeof(record)) {
    return false;
  }

  if (!InternalFS.rename(TEMP_PATH, RECORD_PATH)) {
    return false;
  }

  SequenceRecord verified = {};
  return readRecord(&verified) &&
         verified.reservedUntil == newEnd;
}

bool reserveBlock() {
  if (!storageReady ||
      nextSequence > MAX_SEQUENCE - (RESERVATION_SIZE - 1)) {
    storageReady = false;
    return false;
  }

  const uint32_t newEnd = nextSequence + RESERVATION_SIZE - 1;

  if (!saveReservation(newEnd)) {
    storageReady = false;
    return false;
  }

  reservationEnd = newEnd;
  return true;
}

}  // namespace

bool initializeSequenceStorage() {
  storageReady = false;

  // Explicitly call the non-formatting parent implementation.
  if (!InternalFS.Adafruit_LittleFS::begin()) {
    return false;
  }

  SequenceRecord record = {};
  if (!readRecord(&record)) {
    return false;
  }

  // A stored UINT32_MAX cannot be advanced safely.
  if (record.reservedUntil == MAX_SEQUENCE) {
    return false;
  }

  nextSequence = record.reservedUntil + 1;
  storageReady = true;

  return reserveBlock();
}

bool getNextPersistentSequence(uint32_t* sequence) {
  if (!storageReady || sequence == nullptr) {
    return false;
  }

  if (nextSequence > reservationEnd && !reserveBlock()) {
    return false;
  }

  if (nextSequence == UINT32_MAX) {
    storageReady = false;
    return false;
  }
  *sequence = nextSequence;
  ++nextSequence;
  return true;
}

// Explicit provisioning only. Never call during normal startup.
// Use only on a verified fresh device with a newly generated AES key.
bool provisionSequenceStorage() {
  storageReady = false;

  if (!InternalFS.Adafruit_LittleFS::begin()) {
    return false;
  }

  // Refuse to overwrite existing or interrupted provisioning data.
  if (InternalFS.exists(RECORD_PATH) || InternalFS.exists(TEMP_PATH)) {
    return false;
  }

  // Reserve sequence 0 as a marker; normal operation starts at 1.
  return saveReservation(0);
}
