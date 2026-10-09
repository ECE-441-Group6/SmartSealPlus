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
* Camera/Image Storage

↓

User Dashboard

* Temperature Monitoring
* Tamper Alerts
* Event History
* Image Evidence

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
* Dashboard event history
* Raspberry Pi camera capture for tamper and vibration events
* Captured image links in the dashboard

## Planned Features

* Real sensor integration
* BLE communication between ESP32-C3 and Raspberry Pi
* Temperature threshold alerts
* Tamper detection alerts
* Vibration event monitoring
* Production BLE communication between ESP32-C3 and Raspberry Pi
* Cloud image upload

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

## Run the gateway and dashboard

Install the Python dependencies, then open two terminals from the repository root:

```text
python3 -m pip install -r requirements.txt
python3 Gateway/gateway_main.py
python3 Dashboard/dashboard.py
```

Open `http://127.0.0.1:5000`. The gateway currently generates simulated ESP32 advertisements every five seconds, stores readings in `Gateway/smartseal.db`, and the dashboard refreshes the readings automatically.

When `tamper` or `vibration` is true, the gateway captures a real JPEG with the Raspberry Pi camera, saves it in `Gateway/images/`, stores its filename with the event, and displays a `View` link in the dashboard. The gateway keeps one camera session open while it runs and closes it when the process exits.

On a non-Raspberry Pi development computer, or when `picamera2` is unavailable, Pillow creates a labeled simulated camera frame instead. Without `OPENAI_API_KEY`, the AI result uses the sensor evidence as a local fallback. Set `OPENAI_API_KEY` to enable vision analysis through the configured `OPENAI_VISION_MODEL` (default `gpt-4o-mini`).

### Test the camera directly

To verify the attached Raspberry Pi camera without waiting for a sensor event:

```text
python3 Gateway/gateway_camera.py
```

Choose `1` to capture a test image or `2` to capture a tamper-event image. Images are written to `Gateway/images/`.
