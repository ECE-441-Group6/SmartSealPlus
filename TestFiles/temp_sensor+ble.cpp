#include <OneWire.h>
#include <DallasTemperature.h>

#include <BLEDevice.h>
#include <BLEAdvertising.h>
#include <BLEUtils.h>
#include <BLEBeacon.h>

#define ONE_WIRE_BUS 4

#define SEAL_ID 1
#define MANUFACTURER_ID 0x5353

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

BLEAdvertising* advertising;

unsigned long lastUpdate = 0;
const unsigned long UPDATE_INTERVAL = 5000;

float readTemperatureC() {
  sensors.requestTemperatures();

  float temperature = sensors.getTempCByIndex(0);

  if (temperature == DEVICE_DISCONNECTED_C) {
    Serial.println("ERROR: DS18B20 disconnected.");
    return NAN;
  }

  return temperature;
}

void updateAdvertisement(float temperature) {
  if (isnan(temperature)) {
    Serial.println("Skipping advertisement: invalid temperature.");
    return;
  }

  // Example payload: S:1,T:23.5,A:0,V:0
  char payload[40];

  snprintf(
    payload,
    sizeof(payload),
    "S:%d,T:%.2f,A:0,V:0",
    SEAL_ID,
    temperature
  );

  BLEAdvertisementData advertisementData;

  advertisementData.setManufacturerData(
    std::string(payload)
  );

  advertising->stop();
  advertising->setAdvertisementData(advertisementData);
  advertising->start();

  Serial.print("Advertising sensor data: ");
  Serial.println(payload);
}

void setup() {
  Serial.begin(115200);

  sensors.begin();

  Serial.print("DS18B20 sensors detected: ");
  Serial.println(sensors.getDeviceCount());

  BLEDevice::init("SmartSeal-01");

  advertising = BLEDevice::getAdvertising();

  Serial.println("SmartSeal+ temperature BLE started.");
}

void loop() {
  unsigned long now = millis();

  if (now - lastUpdate >= UPDATE_INTERVAL) {
    lastUpdate = now;

    float temperature = readTemperatureC();

    if (!isnan(temperature)) {
      Serial.print("Temperature: ");
      Serial.print(temperature, 2);
      Serial.println(" C");

      updateAdvertisement(temperature);
    }
  }
}