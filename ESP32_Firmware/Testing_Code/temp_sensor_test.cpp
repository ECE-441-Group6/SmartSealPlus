#include <OneWire.h>
#include <DallasTemperature.h>

// DS18B20 data wire connected to GPIO 4.
#define ONE_WIRE_BUS 4

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

void setup() {
  Serial.begin(115200);
  delay(1000);

  sensors.begin();

  Serial.println("SmartSeal+ DS18B20 Temperature Test");

  Serial.print("Number of DS18B20 sensors detected: ");
  Serial.println(sensors.getDeviceCount());
}

void loop() {
  sensors.requestTemperatures();

  float temperatureC = sensors.getTempCByIndex(0);

  if (temperatureC == DEVICE_DISCONNECTED_C) {
    Serial.println("ERROR: DS18B20 not detected.");
  } else {
    Serial.print("Temperature: ");
    Serial.print(temperatureC, 2);
    Serial.println(" C");
  }

  delay(2000);
}