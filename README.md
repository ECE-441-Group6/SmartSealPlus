# SmartSeal+

SmartSeal+ monitors a shipment seal using a Seeed XIAO nRF52840 Sense. The
XIAO samples temperature and vibration, broadcasts sensor readings over BLE,
and a Python gateway records events for a local web dashboard.

## Current system

```text
XIAO nRF52840 Sense
  └─ BLE manufacturer advertisements (company ID 0x5353)
       └─ Python gateway + SQLite
            ├─ temperature/vibration alerts
            ├─ optional camera capture and image analysis
            └─ Flask dashboard and CSV session archives
```

The XIAO-to-gateway sensor path uses BLE manufacturer advertisements. The
gateway scans for the SmartSeal manufacturer ID and decodes each binary sensor
packet without opening a GATT connection.
The dashboard communicates with the gateway's local SQLite database through
Flask HTTP endpoints; it does not use BLE.

Tamper detection is not currently installed. The gateway normalizes every
received event's tamper status to `false`. Temperature outside the 2–8 °C
range raises an alert but does not by itself trigger a photo. Vibration events
trigger a camera capture.

## Requirements

- Python 3.10 or later
- A BLE adapter supported by Bleak
- Seeed XIAO nRF52840 Sense and Arduino IDE for hardware firmware
- Raspberry Pi camera for real photographs (optional; Pillow creates a
  simulated image when camera hardware is unavailable)

Install gateway and dashboard dependencies from the repository root:

```bash
python3 -m pip install -r requirements.txt
```

The requirements are Flask, Pillow, and Bleak.

## Upload the XIAO firmware

1. Open `XIAOnRF8540/VT_IntegratedBLE/VT_IntegratedBLE.ino` in Arduino IDE.
2. Select the Seeed XIAO nRF52840 Sense board and its serial port.
3. Upload the sketch.
4. Open Serial Monitor at 115200 baud.
5. Press the record button on D6 to start sampling.

The current firmware configuration in `XIAOnRF8540/VT_IntegratedBLE/config.h`
uses:

- Record button: D6
- Temperature input: A0
- Vibration input: A2
- Temperature sampling: every 5 seconds
- Piezo vibration sampling: approximately 1,000 samples per second while
  recording
- Vibration baseline calibration: first 1,000 samples (about one second) after
  recording starts; keep the seal stationary during calibration
- BLE manufacturer advertisement update: every 5 seconds while recording
- Serial plotter output: every 5 seconds

The firmware reports the calibrated baseline ADC and the calibration noise
standard deviation in Serial Monitor. It detects vibration using the absolute
ADC deviation from the baseline. The provisional threshold is at least 100 ADC
counts, increased to four times the measured calibration noise standard
deviation when that is higher. To reject isolated electrical spikes, at least
three threshold-exceeding samples must occur within a 20 ms window. A further
event is armed after 100 ms below threshold. Detected events are held until the
next advertisement, without changing the existing five-second schedule.

The manufacturer advertisement contains a binary sensor packet:

| Field | Encoding |
|---|---|
| Header and version | `A5 01` |
| Seal ID | 1 byte |
| Event sequence | 4-byte little-endian unsigned integer |
| Temperature | 2-byte little-endian signed integer, tenths of °C |
| Tamper flag | 1 byte |
| Vibration event | 2-byte little-endian unsigned integer (`0` or `100`) |

The gateway accepts the packet using the manufacturer ID and packet format,
not the advertised device name.

## Run the gateway and dashboard

Run each program in a separate terminal from the repository root.

Terminal 1 — XIAO BLE gateway:

```bash
python3 Gateway/gateway_main.py
```

Alternatively, run from the XIAO gateway directory:

```bash
cd Gateway
python3 gateway_main.py
```

Terminal 2 — dashboard:

```bash
python3 Dashboard/dashboard.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The live dashboard polls
the gateway every two seconds and displays a sync time and event count. Use
the **Event history** selector to switch between the current session and
previously archived sessions.

Set `SMARTSEAL_SIMULATION=1` to exercise the gateway without BLE hardware:

```bash
SMARTSEAL_SIMULATION=1 python3 Gateway/gateway_main.py
```

## Event processing and storage

The gateway:

1. Scans for BLE manufacturer advertisements and parses valid SmartSeal
   packets.
2. Validates packet fields and preserves the tamper status.
3. Stores events in `Gateway/smartseal.db`.
4. Raises low-temperature alerts below 2 °C and high-temperature alerts
   above 8 °C.
5. Captures an image for vibration events. Temperature alerts alone do not
   take a picture.
6. Stores image filenames and analysis with events when available.

Rows are unique by `(seal_id, event_sequence)`, so receiving the same sequence
again does not create another database row.

Each gateway start clears the live event and seal-status tables so the
dashboard starts with a fresh session. When stopped with Ctrl+C, the gateway
exports that session's events to a timestamped CSV in `Gateway/archives/`.
For example:

```text
Gateway/archives/gateway-events-20261027-154408-123456.csv
```

Archives remain available after later gateway starts and can be selected in
the dashboard. The CSV stores event values and image filenames; captured
images are stored separately in `Gateway/images/`. A forced process kill or
power loss may prevent the shutdown archive from being written.

## Tests

From the repository root:

```bash
python3 -m unittest Gateway.Test.test_reliability -v
python3 -m py_compile Gateway/packet_parser.py Gateway/ble_scanner.py \
  Gateway/database.py Gateway/gateway_main.py Dashboard/dashboard.py
```

The tests cover packet parsing, tamper normalization, duplicate storage,
event-history clearing, CSV export, and archiving on gateway shutdown.

## Main project paths

```text
XIAOnRF8540/VT_IntegratedBLE/   XIAO Arduino sketch and firmware modules
Gateway/XIAO/                   XIAO BLE advertisement scanner and launcher
Gateway/                         Shared packet handling, alerts, storage, camera
Gateway/archives/                Timestamped CSV archives after gateway shutdown
Gateway/images/                  Captured or simulated camera images
Dashboard/                       Flask app, templates, and browser assets
requirements.txt                 Python dependencies
```
