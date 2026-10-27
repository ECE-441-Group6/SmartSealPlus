/* Creates and periodically broadcasts the BLE advertisement containing SmartSeal data. */
#include "ble_advertising.h"
#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEAdvertising.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <cstdio>
#include <string>

namespace
{
constexpr uint8_t manufacturerIdLowByte = 0x53;
constexpr uint8_t manufacturerIdHighByte = 0x53;
BLEAdvertising* advertising = nullptr;
volatile bool gatewayAcknowledged = false;
volatile uint32_t acknowledgedSequence = 0;
uint32_t advertisedSequence = 0;

class GatewayAckCallbacks : public BLECharacteristicCallbacks
{
    void onWrite(BLECharacteristic* characteristic) override
    {
        std::string value = characteristic->getValue();
        unsigned int sealId = 0;
        unsigned long sequence = 0;
        if (std::sscanf(value.c_str(), "ACK:S:%u,E:%lu", &sealId, &sequence) == 2 &&
            sealId == SMARTSEAL_SEAL_ID &&
            sequence == advertisedSequence)
        {
            acknowledgedSequence = static_cast<uint32_t>(sequence);
            gatewayAcknowledged = true;
        }
    }
};
}

void initBLE()
{
    BLEDevice::init(SMARTSEAL_DEVICE_NAME);
    advertising = BLEDevice::getAdvertising();
    advertising->setScanResponse(false);
    BLEServer* server = BLEDevice::createServer();
    BLEService* service = server->createService(
        "12345678-1234-1234-1234-1234567890ab");
    BLECharacteristic* acknowledgement = service->createCharacteristic(
        "12345678-1234-1234-1234-1234567890ad",
        BLECharacteristic::PROPERTY_WRITE);
    acknowledgement->setCallbacks(new GatewayAckCallbacks());
    service->start();

    Serial.println("BLE initialized");
}

void publishBLEAdvertisement(SensorData data, uint32_t sequence)
{
    if (advertising == nullptr)
    {
        Serial.println("BLE update skipped: BLE is not initialized");
        return;
    }

    char payload[40];
    std::snprintf(
        payload,
        sizeof(payload),
        "S:%d,E:%lu,T:%.1f,A:%d,V:%d",
        SMARTSEAL_SEAL_ID,
        static_cast<unsigned long>(sequence),
        static_cast<double>(data.temperature),
        data.tamper ? 1 : 0,
        data.vibration ? 1 : 0);

    // BLEAdvertisementData expects the two-byte company ID at the start of
    // the raw manufacturer field. Bleak removes these bytes before parsing.
    String manufacturerData;
    manufacturerData += static_cast<char>(manufacturerIdLowByte);
    manufacturerData += static_cast<char>(manufacturerIdHighByte);
    manufacturerData += payload;

    BLEAdvertisementData advertisementData;
    advertisementData.setFlags(0x06);
    // Keep the sensor packet in the primary legacy advertisement. Including
    // the 15-character name here can exceed the 31-byte BLE limit and cause
    // scanners to miss the manufacturer data.
    advertisementData.setManufacturerData(manufacturerData);

    advertising->stop();
    advertising->setAdvertisementData(advertisementData);
    advertising->start();

    Serial.print("Advertising: ");
    Serial.println(payload);
}

void updateBLEAdvertisement(SensorData data)
{
    publishBLEAdvertisement(data, ++advertisedSequence);
}

void repeatBLEAdvertisement(SensorData data)
{
    publishBLEAdvertisement(data, advertisedSequence);
}

bool waitForGatewayAcknowledgement()
{
    gatewayAcknowledged = false;
    const unsigned long start = millis();
    while (!gatewayAcknowledged &&
           millis() - start < SMARTSEAL_ACK_TIMEOUT_MS)
    {
        delay(10);
    }

    if (!gatewayAcknowledged)
    {
        Serial.println("Gateway acknowledgment timeout; retrying packet.");
    }
    return gatewayAcknowledged;
}

bool isCriticalEvent(SensorData data)
{
    return data.tamper || data.temperature < 2.0f || data.temperature > 8.0f;
}