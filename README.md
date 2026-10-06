# SmartSeal+

SmartSeal+ is a low-cost active smart seal designed for medical cold-chain transportation. The system combines tamper detection, temperature monitoring, vibration sensing, and wireless communication to provide real-time shipment monitoring and alerts.

## Team Members

* Zifeng Huang — ESP32-C3 firmware, BLE communication, sensor integration, event detection
* Jessica Perez — SmartSeal hardware design, POF tamper detection, sensor integration
* Sadek Mezine — Raspberry Pi gateway, dashboard development, data storage, cloud and camera integration

## Project Overview

The SmartSeal device uses an ESP32-C3 microcontroller to monitor:

* POF-based tamper detection
* Temperature using a DS18B20 sensor
* Vibration and impact events

Sensor information is transmitted to a Raspberry Pi gateway using Bluetooth Low Energy (BLE) advertising.

The gateway receives sensor data, stores events, generates alerts, and displays status information through a monitoring dashboard.

## System Architecture

SmartSeal Device (ESP32-C3)

* Temperature Sensor
* POF Tamper Detection
* Vibration Sensor
* BLE Advertising

↓

Raspberry Pi Gateway

* BLE Receiver
* Event Processing
* Database Storage
* Dashboard
* Camera/Image Storage (Future Enhancement)

↓

User Dashboard

* Temperature Monitoring
* Tamper Alerts
* Event History
* I
