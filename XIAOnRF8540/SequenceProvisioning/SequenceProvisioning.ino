#include <Arduino.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include <stdint.h>

using namespace Adafruit_LittleFS_Namespace;

const char* const RECORD_PATH = "/sequence.dat";
const char* const TEMP_PATH = "/sequence.tmp";
constexpr uint32_t RECORD_MAGIC = 0x53535131;

struct SequenceRecord {
  uint32_t magic;
  uint32_t reservedUntil;
  uint32_t checksum;
};

void setup() {
  Serial.begin(115200);
  delay(3000);

  Serial.println("SmartSeal+ one-time sequence provisioning");

  if (!InternalFS.Adafruit_LittleFS::begin()) {
    Serial.println("FAILED: Filesystem unavailable.");
    return;
  }

  if (InternalFS.exists(RECORD_PATH) || InternalFS.exists(TEMP_PATH)) {
    Serial.println("REFUSED: Existing sequence data detected.");
    return;
  }

  SequenceRecord record = {
    RECORD_MAGIC,
    0,
    RECORD_MAGIC ^ 0xA5A55A5A
  };

  File file(InternalFS);
  if (!file.open(TEMP_PATH, FILE_O_WRITE)) {
    Serial.println("FAILED: Cannot create temporary record.");
    return;
  }

  size_t written = file.write(
    reinterpret_cast<const uint8_t*>(&record),
    sizeof(record)
  );
  file.flush();
  file.close();

  if (written != sizeof(record) ||
      !InternalFS.rename(TEMP_PATH, RECORD_PATH)) {
    Serial.println("FAILED: Cannot save sequence record.");
    return;
  }

  Serial.println("SUCCESS: Initial sequence record created.");
}

void loop() {}
