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

The ESP32 simulation sketch generates a random temperature between `1.00 C` and
`10.00 C`, plus occasional simulated tamper and vibration events. It advertises
packets such as `S:1,T:4.50,A:0,V:1` using manufacturer ID `0x5353`. On the
Raspberry Pi, the gateway scans for `SmartSeal-01`, parses each packet, and
processes it through the normal alert, camera, AI, database, and dashboard flow.
The ESP32 publishes one reading every five seconds, matching the Pi's five-second
BLE scan window. The Pi starts the next scan immediately after processing a valid
reading.

The XIAO nRF52840 integrated recorder is organized as an Arduino sketch in
`XIAOnRF8540/VT_IntegratedBLE/`. Open `VT_IntegratedBLE.ino` to upload it; the
supporting `main.cpp`, sensor manager, BLE manager, and configuration files are
compiled as part of the same sketch.
The recorder keeps its existing recording characteristic and also exposes the
XIAO test interface as `SmartSeal-XIAO` with service `0x180F` and characteristic
`0x2A19`. The gateway reads the sensor packet from that characteristic when no
ESP32 manufacturer advertisement is available, so ESP32 connectivity remains
supported. XIAO packets use the `V` field for the measured vibration voltage
(for example, `S:1,T:63.4,A:0,V:2.20`); ESP32 packets continue to use `V` as
their vibration event flag.
Start the gateway only after uploading
`ESP32_Firmware/Simulation_Placeholders/Simulation_Placeholders.ino` to the
ESP32. For development without the ESP32, run `SMARTSEAL_SIMULATION=1
python3 Gateway/gateway_main.py`.

On a non-Raspberry Pi development computer, or when `picamera2` is unavailable, Pillow creates a labeled simulated camera frame instead. Without `OPENAI_API_KEY`, the AI result uses the sensor evidence as a local fallback. Set `OPENAI_API_KEY` to enable vision analysis through the configured `OPENAI_VISION_MODEL` (default `gpt-4o-mini`).

### Test the camera directly

To verify the attached Raspberry Pi camera without waiting for a sensor event:

```text
python3 TestFiles/gateway_camera.py
```

Choose `1` to capture a test image or `2` to capture a tamper-event image. Images are written to `Gateway/images/`.

## Run ESP32 tests in Arduino IDE

1. Install the Espressif ESP32 board package through Arduino IDE's Boards Manager.
2. Connect the ESP32 and select the correct board and port. This project targets `ESP32C3 Dev Module`; select a different ESP32 board only when using different hardware.
3. To build the simulation firmware, open `ESP32_Firmware/Simulation_Placeholders/Simulation_Placeholders.ino`. It uses simulated sensor readings (`4.5 C`, no tamper, no vibration), serial-only alerts, and broadcasts the gateway packet format.
4. Open one test at a time from `TestFiles/`:
	* `esp32_connection_test.cpp` checks serial output.
	* `esp32_ble_test.cpp` advertises the device name `SmartSeal-01` and manufacturer data.
5. For the most reliable Arduino IDE workflow, place each `.cpp` test file in its own sketch folder with a matching `.ino` file, or open a copy renamed to `.ino`.
6. Upload the sketch and open Serial Monitor at `115200` baud.

The BLE test uses advertising, not a GATT service. To inspect it from a computer or Raspberry Pi, install the scanner dependency and run:

```text
python3 -m pip install bleak
python3 TestFiles/verify_smartseal_ble.py
```

`verify_smartseal_ble.py` listens for manufacturer data with company ID `0x5353` in three-second scan cycles, decodes the sensor payload as UTF-8, and prints it in the format `[SmartSeal-01] message`. The packet is identified by its company ID and format even when the BLE name is omitted to stay within the legacy advertisement size limit. Repeated messages are suppressed, so output appears only when a new BLE message is received. Press `Ctrl+C` to stop the monitor.

The GPS scripts require a Raspberry Pi or another host with a connected GPS serial device. Install `pyserial` for `gps_test.py`, and install both `pyserial` and `pynmea2` for `gps_readable.py`. Update the serial port in the script if the GPS is not connected at `/dev/ttyAMA0`.
