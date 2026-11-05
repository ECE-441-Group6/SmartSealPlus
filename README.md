# SmartSeal+

SmartSeal+ monitors a shipment seal using a Seeed XIAO nRF52840 Sense. The XIAO samples temperature and vibration, broadcasts
sensor readings over BLE, and a Python gateway records events for a local web
dashboard.

## Current system

```text
XIAO nRF52840 Sense
  ├─ BLE manufacturer advertisements (company ID 0x5353)
  │    └─ Gateway/ble_scanner.py → Gateway/gateway_main.py
  └─ Optional BLE GATT JSON notifications
       └─ Gateway/GATT/gatt_gateway_main.py

Python gateway + SQLite
  ├─ temperature/vibration alerts
  ├─ optional camera capture and image analysis
  └─ Flask dashboard and CSV session archives
```

The default XIAO advertisement path encrypts sensor packets with AES-128-CCM
using a distinct key per seal. The optional GATT gateway is a separate
prototype and does not use this advertisement encryption.
An alternate GATT gateway is available
for firmware that exposes the UUIDs in `Gateway/GATT/gatt_ble_scanner.py`; it
receives JSON notifications, monitors heartbeats, and acknowledges sensor
events.

The dashboard communicates with the local SQLite database through Flask HTTP
endpoints; it does not use BLE.

The advertising firmware does not include a separate tamper sensor;
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

On Raspberry Pi OS, install the gateway and dashboard dependencies as
OS-managed packages. This works with the system `python3` without a virtual
environment and avoids PEP 668's blocked system-wide `pip` installs:

```bash
sudo apt update
sudo apt install python3-bleak python3-flask python3-pil python3-cryptography
```

The Python requirements are Flask, Pillow, Bleak, and Cryptography.

## Provision encryption keys

Generate a fresh 128-bit key for each seal from the repository root:

```bash
python3 -m Gateway.provision_seal_key 1
```

This writes the gateway registry to `Gateway/keys.json` and the matching
firmware header to `XIAOnRF8540/Advertising/secrets.h`. Both files are ignored
by Git and written with owner-only permissions. Do not copy their contents
into source files, commit them, or reuse a key for another seal. The command
can also use custom locations:

```bash
python3 -m Gateway.provision_seal_key 1 \
  --registry /secure/path/keys.json \
  --firmware-header /secure/path/secrets.h
```

Set the gateway environment variable to the same registry in the terminal
that will run the gateway. Use an absolute path, especially when starting the
gateway from `Gateway/XIAO`:

```bash
export SMARTSEAL_KEY_REGISTRY="/absolute/path/to/SmartSealPlus/Gateway/keys.json"
```

The registry must be a non-empty JSON object mapping decimal seal IDs to
Base64-encoded 16-byte keys, and on POSIX systems it must not be readable by
group or other users (`chmod 600 Gateway/keys.json`). Real BLE scanning fails
closed if the environment variable, file, permissions, encoding, or key length
is invalid. Simulation mode does not load real keys.

## Upload the XIAO firmware

1. Open the XIAO firmware sketch you want to use in Arduino IDE:
   `XIAOnRF8540/Advertising/Advertising.ino` for BLE advertising, or
   `XIAOnRF8540/VT_IntegratedBLE.cpp` for the integrated/GATT experiment.
2. In Arduino IDE Library Manager, install **Crypto** by Rhys Weatherley.
3. Generate the private `secrets.h` as described above; do not use the
   all-zero example key.
4. Select the Seeed XIAO nRF52840 Sense board and its serial port.
5. Upload the sketch.
6. Open Serial Monitor at 115200 baud.
7. Press the record button on D6 to start sampling.

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
- Manufacturer advertisement: every 5 seconds
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

The encrypted advertising gateway accepts manufacturer ID `0x5353` and
version-2 packets only. The advertisement's 26-byte payload is version `2`,
a 7-byte hardware-random nonce, 10 bytes of AES-CCM ciphertext, and an
8-byte authentication tag. The encrypted plaintext contains the seal ID,
4-byte little-endian event sequence, signed temperature in tenths of a degree
Celsius, tamper byte, and 2-byte little-endian vibration in hundredths of a
volt. The version byte is authenticated as additional data. The seal ID is
inside the ciphertext and is checked against the key that successfully
authenticated the packet. Plaintext, legacy, malformed, tampered, unknown-seal,
and unauthenticated packets are rejected.

The ciphertext and authentication tag fit in a BLE manufacturer data field;
the XIAO name is sent in the scan response. Encryption protects sensor
contents and authenticates packets, but does not hide the device's presence or
prevent replay of a previously captured valid packet.

In Arduino IDE, open `XIAOnRF8540/Advertising/Advertising.ino`, build, and
upload it to the XIAO. Open Serial Monitor at 115200 baud and press D6; the
firmware sends sensor advertisements after recording starts. The serial
monitor reports BLE initialization or advertisement-update failures.

## Run the gateway and dashboard

Run each program in a separate terminal.

Terminal 1 — XIAO advertisement gateway. From the project root:

```bash
cd Gateway/XIAO
python3 gateway_main.py
```

Or run it from the project root:

```bash
python3 Gateway/XIAO/gateway_main.py
```

The scanner listens for up to 5 seconds per attempt. Press D6 to start
recording, then wait for the next advertisement. If it receives no packet,
its output distinguishes no BLE traffic, missing manufacturer data, and an
unexpected packet format. Make sure the XIAO is running the matching
`XIAOnRF8540/Advertising/Advertising.ino` firmware, Bluetooth is enabled, and
the adapter is available to the account running Python.

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

Simulation generates gateway packets in memory. The GATT gateway does not
use this simulation mode.

## Event processing and storage

The advertisement gateway:

1. Scans BLE manufacturer advertisements for company ID `0x5353`.
2. Requires the version-2 AES-CCM packet, validates its tag, and checks its
   authenticated seal ID against the matching registered key.
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
python3 -m unittest tests.test_ble_advertisements -v
python3 -m py_compile Gateway/packet_parser.py Gateway/ble_scanner.py \
  Gateway/key_registry.py Gateway/provision_seal_key.py \
  Gateway/database.py Gateway/gateway_main.py Dashboard/dashboard.py
```

The reliability tests cover packet decoding, duplicate storage,
event-history clearing, vibration alerts, CSV export, and archiving on gateway
shutdown. The BLE advertisement tests cover registered and incorrect keys,
unknown and forged seal IDs, registry errors, tampered tags, malformed packets,
plaintext and legacy rejection, and receipt by both gateway scanners.
`py_compile` only checks Python syntax; it does not execute the gateway or
tests.

## Main project paths

```text
XIAOnRF8540/Advertising/         XIAO manufacturer-advertising firmware
XIAOnRF8540/VT_IntegratedBLE.cpp Integrated BLE/GATT firmware experiment
Gateway/                         Shared packet handling, alerts, storage, camera
Gateway/GATT/                    Persistent BLE GATT scanner and gateway
Gateway/XIAO/ and Gateway/ESP32/ BLE scanner entry points
Gateway/archives/                Timestamped CSV archives after gateway shutdown
Gateway/images/                  Captured or simulated camera images
Dashboard/                       Flask app, templates, and browser assets
requirements.txt                 Python dependencies
```
