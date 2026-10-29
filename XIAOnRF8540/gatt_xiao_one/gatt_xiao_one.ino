
#include <bluefruit.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

// ============================================================
// BLUETOOTH UUIDS
// Must match the Raspberry Pi gateway code.
// ============================================================

// Sensor data service and characteristic.
static BLEService sensorService(
    "12345678-1234-1234-1234-1234567890ab"
);

static BLECharacteristic sensorCharacteristic(
    "12345678-1234-1234-1234-1234567890ac"
);

// Communication/connection-health service.
static BLEService communicationService(
    "12345678-1234-1234-1234-1234567890ad"
);

// XIAO -> Pi: heartbeat notifications.
static BLECharacteristic heartbeatCharacteristic(
    "12345678-1234-1234-1234-1234567890ae"
);

// Pi -> XIAO: packet acknowledgment writes.
static BLECharacteristic acknowledgmentCharacteristic(
    "12345678-1234-1234-1234-1234567890af"
);

// ============================================================
// CONFIGURATION
// ============================================================

static const char DEVICE_NAME[] = "SmartSeal-XIAO";

static const unsigned long HEARTBEAT_INTERVAL_MS = 2000;

// ============================================================
// STATE
// ============================================================

static unsigned long lastHeartbeatMs = 0;
static uint32_t heartbeatCounter = 0;

static volatile uint32_t lastAcknowledgedSequence = 0;
static volatile bool acknowledgmentReceived = false;

// ============================================================
// CONNECTION CALLBACKS
// ============================================================

static void connectCallback(uint16_t connectionHandle) {
    (void)connectionHandle;

    Serial.println("BLE: Raspberry Pi connected.");

    lastHeartbeatMs = millis();
}

static void disconnectCallback(
    uint16_t connectionHandle,
    uint8_t reason
) {
    (void)connectionHandle;

    Serial.print("BLE: Disconnected. Reason: ");
    Serial.println(reason);
}

// ============================================================
// ACKNOWLEDGMENT CALLBACK
// Raspberry Pi writes a 4-byte little-endian sequence number.
// ============================================================

static void acknowledgmentWriteCallback(
    uint16_t connectionHandle,
    BLECharacteristic* characteristic,
    uint8_t* data,
    uint16_t length
) {
    (void)connectionHandle;
    (void)characteristic;

    if (length != 4) {
        Serial.println("BLE: Invalid acknowledgment length.");
        return;
    }

    uint32_t sequence =
        ((uint32_t)data[0]) |
        ((uint32_t)data[1] << 8) |
        ((uint32_t)data[2] << 16) |
        ((uint32_t)data[3] << 24);

    lastAcknowledgedSequence = sequence;
    acknowledgmentReceived = true;
}

// ============================================================
// INITIALIZE BLUETOOTH
// Called once by setup() in Main.cpp.
// ============================================================

void setupBLE() {
    Bluefruit.begin();

    Bluefruit.setName(DEVICE_NAME);
    Bluefruit.setTxPower(0);

    Bluefruit.Periph.setConnectCallback(connectCallback);
    Bluefruit.Periph.setDisconnectCallback(disconnectCallback);

    // --------------------------------------------------------
    // Sensor service
    // --------------------------------------------------------

    sensorService.begin();

    sensorCharacteristic.setProperties(
        CHR_PROPS_NOTIFY
    );

    sensorCharacteristic.setPermission(
        SECMODE_OPEN,
        SECMODE_NO_ACCESS
    );

    sensorCharacteristic.setMaxLen(200);
    sensorCharacteristic.begin();

    // --------------------------------------------------------
    // Communication service
    // --------------------------------------------------------

    communicationService.begin();

    // Heartbeat: XIAO sends a 4-byte counter to the Pi.
    heartbeatCharacteristic.setProperties(
        CHR_PROPS_NOTIFY
    );

    heartbeatCharacteristic.setPermission(
        SECMODE_OPEN,
        SECMODE_NO_ACCESS
    );

    heartbeatCharacteristic.setFixedLen(4);
    heartbeatCharacteristic.begin();

    // Acknowledgment: Pi writes a 4-byte sequence number.
    acknowledgmentCharacteristic.setProperties(
        CHR_PROPS_WRITE
    );

    acknowledgmentCharacteristic.setPermission(
        SECMODE_OPEN,
        SECMODE_OPEN
    );

    acknowledgmentCharacteristic.setFixedLen(4);

    acknowledgmentCharacteristic.setWriteCallback(
        acknowledgmentWriteCallback
    );

    acknowledgmentCharacteristic.begin();

    // --------------------------------------------------------
    // Advertising
    // --------------------------------------------------------

    Bluefruit.Advertising.addFlags(
        BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE
    );

    Bluefruit.Advertising.addTxPower();

    // Advertise the sensor service so the Pi can discover us.
    Bluefruit.Advertising.addService(sensorService);

    Bluefruit.ScanResponse.addName();

    Bluefruit.Advertising.restartOnDisconnect(true);
    Bluefruit.Advertising.setInterval(32, 244);
    Bluefruit.Advertising.setFastTimeout(30);

    Bluefruit.Advertising.start(0);

    Serial.println("BLE initialized.");
    Serial.print("Device name: ");
    Serial.println(DEVICE_NAME);
    Serial.println("Advertising started.");
}

// ============================================================
// SEND SENSOR PACKET
//
// JSON fields must match the Raspberry Pi decoder:
//
// {
//   "seal_id": 1,
//   "event_sequence": 0,
//   "temperature": 72.5,
//   "tamper": false,
//   "vibration": 1.23
// }
//
// Temperature is null if the thermistor reading is invalid.
// Vibration is the voltage supplied by Main.cpp.
// ============================================================

bool sendSensorPacket(
    uint32_t sealID,
    uint32_t eventSequence,
    float temperature,
    bool tamper,
    float vibration
) {
    if (!Bluefruit.connected()) {
        return false;
    }

    if (!isfinite(vibration) || vibration < 0.0f) {
        return false;
    }

    char jsonPacket[128];
    int packetLength;

    if (isfinite(temperature)) {
        packetLength = snprintf(
            jsonPacket,
            sizeof(jsonPacket),
            "{\"seal_id\":%lu,"
            "\"event_sequence\":%lu,"
            "\"temperature\":%.2f,"
            "\"tamper\":%s,"
            "\"vibration\":%.3f}",
            (unsigned long)sealID,
            (unsigned long)eventSequence,
            temperature,
            tamper ? "true" : "false",
            vibration
        );
    } else {
        packetLength = snprintf(
            jsonPacket,
            sizeof(jsonPacket),
            "{\"seal_id\":%lu,"
            "\"event_sequence\":%lu,"
            "\"temperature\":null,"
            "\"tamper\":%s,"
            "\"vibration\":%.3f}",
            (unsigned long)sealID,
            (unsigned long)eventSequence,
            tamper ? "true" : "false",
            vibration
        );
    }

    if (packetLength <= 0 ||
        packetLength >= (int)sizeof(jsonPacket)) {
        Serial.println("BLE: Sensor packet formatting failed.");
        return false;
    }

    bool success = sensorCharacteristic.notify(
        (const uint8_t*)jsonPacket,
        (uint16_t)packetLength
    );

    return success;
}

// ============================================================
// SEND HEARTBEAT
// Called repeatedly by Main.cpp.
// Actual transmission is limited to the heartbeat interval.
// ============================================================

void sendHeartbeat() {
    unsigned long now = millis();

    if (!Bluefruit.connected()) {
        return;
    }

    if (now - lastHeartbeatMs < HEARTBEAT_INTERVAL_MS) {
        return;
    }

    lastHeartbeatMs = now;
    heartbeatCounter++;

    uint8_t heartbeatData[4];

    heartbeatData[0] =
        (uint8_t)(heartbeatCounter & 0xFF);

    heartbeatData[1] =
        (uint8_t)((heartbeatCounter >> 8) & 0xFF);

    heartbeatData[2] =
        (uint8_t)((heartbeatCounter >> 16) & 0xFF);

    heartbeatData[3] =
        (uint8_t)((heartbeatCounter >> 24) & 0xFF);

    heartbeatCharacteristic.notify(
        heartbeatData,
        sizeof(heartbeatData)
    );
}

// ============================================================
// READ ACKNOWLEDGMENT
// Main.cpp calls this to check whether the Pi wrote an ACK.
// ============================================================

bool getAcknowledgment(uint32_t* sequence) {
    if (sequence == nullptr) {
        return false;
    }

    if (!acknowledgmentReceived) {
        return false;
    }

    noInterrupts();

    *sequence = lastAcknowledgedSequence;
    acknowledgmentReceived = false;

    interrupts();

    return true;
}

