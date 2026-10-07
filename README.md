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
* Image Evidence (Future Enhancement)

## Repository Structure

```text
ESP32_Firmware/
Gateway/
Dashboard/
Documentation/
```

## Current Features

* Simulated sensor data
* BLE packet framework
* Alert processing
* Event database
* Dashboard prototype

## Planned Features

* Real sensor integration
* BLE communication between ESP32-C3 and Raspberry Pi
* Temperature threshold alerts
* Tamper detection alerts
* Vibration event monitoring
* Camera activation upon tamper detection
* Image storage and dashboard integration

## Technologies

### Firmware

* C++
* ESP32-C3
* Arduino Framework / PlatformIO

### Gateway

* Python
* SQLite

### Dashboard

* Flask
* HTML
* CSS
* JavaScript

## Project Status

In Development

Current focus:

* Software architecture
* Dashboard implementation
* BLE communication design
* Hardware procurement and integration

## Run the simulation

Install the dashboard dependency, then open two terminals from the repository root:

```text
python -m pip install -r requirements.txt
python Gateway/gateway_main.py
python Dashboard/dashboard.py
```

Open `http://127.0.0.1:5000`. The gateway simulates an ESP32 advertisement every five seconds, stores it in `Gateway/smartseal.db`, and the dashboard refreshes the readings automatically.

When `tamper` or `vibration` is true, the gateway captures an image and shows a `View` link plus an analysis in the dashboard. On a Raspberry Pi with `picamera2`, the image comes from the camera. On a development computer, Pillow creates a simulated camera frame. Without `OPENAI_API_KEY`, the AI result uses the sensor evidence as a local fallback; set `OPENAI_API_KEY` to enable vision analysis through the configured `OPENAI_VISION_MODEL` (default `gpt-4o-mini`).
