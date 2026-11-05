# SmartSeal+

SmartSeal+ monitors a shipment seal using a Seeed XIAO nRF52840 Sense. The XIAO samples temperature and vibration, broadcasts
sensor readings over BLE, and a Python gateway records events for a local web
dashboard.

## Current system

```text
XIAO nRF52840 Sense
  ├─ Encrypted BLE manufacturer advertisements (company ID 0x5353)
  │    └─ Gateway/ble_scanner.py → Gateway/gateway_main.py
  └─ Optional BLE GATT JSON notifications
       └─ Gateway/GATT/gatt_gateway_main.py

Python gateway + SQLite
  ├─ temperature/vibration alerts
  ├─ optional camera capture and image analysis
  └─ Flask dashboard and CSV session archives
```

The default gateway path is encrypted BLE manufacturer advertising. The
gateway accepts only version-2 AES-CCM packets and rejects unauthenticated
legacy binary and plaintext packets. An alternate GATT gateway is available
for firmware that exposes the UUIDs in `Gateway/GATT/gatt_ble_scanner.py`; it
receives JSON notifications, monitors heartbeats, and acknowledges sensor
events.

The dashboard communicates with the local SQLite database through Flask HTTP
endpoints; it does not use BLE.

The encrypted advertising firmware does not include a separate tamper sensor;
its tamper field is always `false` and vibration is reported separately. The
GATT firmware can provide a boolean `tamper` field. Temperature outside the
2–8 °C range raises an alert but does not by itself trigger a photo. Tamper or
vibration events trigger a camera capture.

## Requirements

- Python 3.10 or later
- A BLE adapter supported by Bleak
- Seeed XIAO nRF52840 Sense and Arduino IDE for hardware firmware
- Raspberry Pi camera for real photographs (optional; Pillow creates a
  simulated image when camera hardware is unavailable)

Install gateway and dashboard dependencies from a virtual environment. This
avoids system-wide package changes and works on Raspberry Pi OS versions that
enforce PEP 668:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `venv` is unavailable on Raspberry Pi OS, install it with
`sudo apt install python3-venv` and retry. Keep the environment activated when
running the gateway.

The requirements are Flask, Pillow, Bleak, and cryptography.

## Upload the XIAO firmware

1. Open the XIAO firmware sketch you want to use in Arduino IDE:
   `XIAOnRF8540/Advertising/Advertising.ino` for encrypted advertising, or
   `XIAOnRF8540/VT_IntegratedBLE.cpp` for the integrated/GATT experiment.
2. Select the Seeed XIAO nRF52840 Sense board and its serial port.
3. Upload the sketch.
4. Open Serial Monitor at 115200 baud.
5. Press the record button on D6 to start sampling.

The current firmware configuration in `XIAOnRF8540/Advertising/config.h`
uses:

- Record button: D6
- Temperature input: A0
- Vibration input: A2
- Temperature sampling: every 5 seconds
- Piezo vibration sampling: approximately 1,000 samples per second while
  recording
- Vibration baseline calibration: first 1,000 samples (about one second) after
  recording starts; keep the seal stationary during calibration
- Encrypted manufacturer advertisement: every 5 seconds
- Serial plotter output: every 5 seconds

The firmware reports the calibrated baseline ADC and the calibration noise
standard deviation in Serial Monitor. It detects vibration using the absolute
ADC deviation from the baseline. The provisional threshold is at least 100 ADC
counts, increased to four times the measured calibration noise standard
deviation when that is higher. To reject isolated electrical spikes, at least
three threshold-exceeding samples must occur within a 20 ms window. A further
event is armed after 100 ms below threshold. Detected events are held until the
next advertisement, without changing the existing five-second schedule.

The GATT sensor notification contains a JSON packet with these fields:

| Field | Type |
|---|---|
| `seal_id` | Integer |
| `event_sequence` | 32-bit unsigned integer |
| `temperature` | Number in °C |
| `tamper` | Boolean vibration-event flag |
| `vibration` | Number in volts |

The gateway writes the acknowledged event sequence to the ACK characteristic
using a 4-byte little-endian integer.

The advertising gateway identifies packets by manufacturer ID `0x5353` and
authenticated packet format, not by the advertised device name. The
advertising firmware's device name is `Xiao_Recorder`.

The XIAO `Advertising` firmware encrypts its manufacturer payload with
AES-CCM. Generate a unique key for each seal and keep both the firmware
secret and gateway registry outside source control. Build and upload the
firmware after provisioning, so the uploaded firmware and gateway registry
contain the same key:

```bash
python -m Gateway.provision_seal_key 1 \
  --registry Gateway/keys.json \
  --firmware-header XIAOnRF8540/Advertising/secrets.h
```

Provisioning generates a new key and replaces the key for that seal. Do not
repeat it for an already provisioned seal unless you intend to rebuild and
re-upload its firmware with the new key.

In Arduino IDE, open `XIAOnRF8540/Advertising/Advertising.ino`, build, and
upload it to the XIAO. Open Serial Monitor at 115200 baud and press D6; the
firmware only sends encrypted sensor advertisements after recording starts.
The advertisements are non-connectable because the gateway only receives
broadcasts. The serial monitor reports BLE initialization, encryption, or
advertisement-update failures.

In PowerShell, set the environment variable this way:

```powershell
python3 Gateway/provision_seal_key.py 1 `
  --registry Gateway/keys.json `
  --firmware-header XIAOnRF8540/Advertising/secrets.h
$env:SMARTSEAL_KEY_REGISTRY = "Gateway/keys.json"
python3 Gateway/gateway_main.py
```

Encrypted advertisements use manufacturer ID `0x5353`, version `2`, a
7-byte random nonce, 10 bytes of encrypted sensor data, and a 6-byte
authentication tag. The gateway rejects packets that fail authentication.
The gateway rejects version-2 packets for unknown seal IDs and requires the
authenticated seal ID to match the key that successfully decrypts the packet.
Legacy version-1 binary and plaintext packets are rejected because they do not
provide authentication or confidentiality.

## Run the gateway and dashboard

Run each program in a separate terminal from the repository root.

Terminal 1 — encrypted advertisement gateway:

```bash
SMARTSEAL_KEY_REGISTRY=Gateway/keys.json python -m Gateway.XIAO.gateway_main
```

PowerShell:

```powershell
$env:SMARTSEAL_KEY_REGISTRY = "Gateway/keys.json"
python -m Gateway.XIAO.gateway_main
```

The XIAO scanner listens for up to 15 seconds per scan. Press D6 to start
recording, then wait for the next encrypted advertisement. If it receives no
packet, its output distinguishes no BLE traffic, missing manufacturer data,
an unexpected packet format, and AES-CCM authentication failures. On
Raspberry Pi OS, run these commands from an activated `.venv` and make sure
Bluetooth is enabled and available to the account running Python.

For the alternate GATT gateway, run:

```bash
python -m Gateway.GATT.gatt_gateway_main
```

Terminal 2 — dashboard:

```bash
python Dashboard/dashboard.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The live dashboard polls
the gateway every two seconds and displays a sync time and event count. Use
the **Event history** selector to switch between the current session and
previously archived sessions.

Set `SMARTSEAL_SIMULATION=1` to exercise the gateway without BLE hardware:

```bash
SMARTSEAL_SIMULATION=1 python -m Gateway.gateway_main
```

In PowerShell:

```powershell
$env:SMARTSEAL_SIMULATION = "1"
python -m Gateway.gateway_main
```

Simulation generates gateway packets in memory and does not require a key
registry. The GATT gateway does not use this simulation mode.

## Event processing and storage

The encrypted-advertisement gateway:

1. Scans BLE manufacturer advertisements for company ID `0x5353`.
2. Authenticates and decrypts version-2 AES-CCM packets.
3. Validates packet fields and stores events in `Gateway/smartseal.db`.
4. Raises low-temperature alerts below 2 °C and high-temperature alerts
   above 8 °C.
5. Captures an image for vibration events. Temperature alerts alone do not
   take a picture.
6. Stores image filenames and analysis with events when available.

The GATT gateway performs the same validation, alerting, storage, camera, and
archive operations while receiving JSON notifications and sending event
sequence acknowledgements.

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
python3 -m unittest tests.test_encrypted_packets -v
python3 -m py_compile Gateway/packet_parser.py Gateway/ble_scanner.py \
  Gateway/database.py Gateway/gateway_main.py Dashboard/dashboard.py
```

The reliability tests cover authenticated packet decoding, duplicate storage,
event-history clearing, vibration alerts, CSV export, and archiving on gateway
shutdown. The encrypted-packet tests cover valid keys, wrong keys, unknown
seals, modified seal IDs, and missing key registries. `py_compile` only checks
Python syntax; it does not execute the gateway or tests.

## Main project paths

```text
XIAOnRF8540/Advertising/         Encrypted XIAO advertising firmware
XIAOnRF8540/VT_IntegratedBLE.cpp Integrated BLE/GATT firmware experiment
Gateway/                         Shared packet handling, alerts, storage, camera
Gateway/GATT/                    Persistent BLE GATT scanner and gateway
Gateway/XIAO/ and Gateway/ESP32/ BLE scanner entry points
Gateway/archives/                Timestamped CSV archives after gateway shutdown
Gateway/images/                  Captured or simulated camera images
Dashboard/                       Flask app, templates, and browser assets
requirements.txt                 Python dependencies
```
