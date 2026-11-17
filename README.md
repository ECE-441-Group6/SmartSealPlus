# SmartSeal+

SmartSeal+ monitors a shipment seal using a Seeed XIAO nRF52840 Sense. The
seal samples temperature, vibration, and movement, then broadcasts an
authenticated, encrypted BLE manufacturer advertisement. A Python gateway
receives the advertisement, records events in SQLite, and serves a Flask
dashboard.

This guide covers the encrypted seal firmware in
`XIAOnRF8540/SmartSeal_Encrypted/` and its BLE advertising gateway. The
advertising gateway supports seal IDs `1` through `255`, with a separate AES
key and nonce prefix configured for each seal.

## System overview

```text
XIAO nRF52840 Sense
  └─ AES-128-CCM BLE manufacturer advertisement (company ID 0x5353)
       └─ Gateway/XIAO/ble_scanner.py
            └─ Gateway/gateway_main.py → SQLite → Flask dashboard
```

The advertisement encrypts the sensor data and authenticates the packet
header. The seal ID and sequence number remain visible. Encryption does not
hide the seal's presence or prevent radio jamming.

## Requirements

Seal hardware:

- Seeed XIAO nRF52840 Sense
- Arduino IDE and the Seeed nRF52 board support package
- The board package's Adafruit Bluefruit and Nordic CryptoCell support
- Thermistor connected to A0, vibration sensor to A2, record button to D6,
  buzzer to D3, and ADXL345 accelerometer on I2C

Sensorless test seal:

- A spare XIAO nRF52840; the Sense model is not required
- No sensors, buttons, jumper wires, or other components are connected
- Arduino IDE and the same Seeed nRF52 board support package used for the seal

Gateway and dashboard:

- Python 3.10 or later
- BLE adapter supported by Bleak
- Dependencies in `requirements.txt`: Flask, Pillow, Bleak, and Cryptography
- Raspberry Pi camera for real photographs (optional; Pillow generates a
  simulated image when camera hardware is unavailable)
- Ollama running locally on the Raspberry Pi for local image analysis
  (optional)

On Raspberry Pi OS, install the system packages:

```bash
sudo apt update
sudo apt install python3-bleak python3-flask python3-pil python3-cryptography
```

On Windows, macOS, or another Linux host, install the Python dependencies in a
virtual environment.

Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configure matching encryption keys

The gateway reads `Gateway/keys.json`. Each seal firmware image reads its own
local `secrets.h` under `XIAOnRF8540/SmartSeal_Encrypted/` or
`XIAOnRF8540/Encrypted_Test_Transmitter/`. Every seal ID must have a matching
entry in the gateway file, and that seal's firmware key and nonce prefix must
match the entry. Use a distinct random AES key and nonce prefix for every seal.
Never use the all-zero example values or commit secret files.

For a brand-new installation, this creates random keys for seals 1 and 2:

```bash
python3 -c 'import json,secrets; from pathlib import Path; ids=(1,2); data={"seals":{str(i):{"SMARTSEAL_AES_KEY":secrets.token_hex(16),"SMARTSEAL_NONCE_PREFIX":secrets.token_hex(9)} for i in ids}}; Path("Gateway/keys.json").write_text(json.dumps(data,indent=2),encoding="utf-8")'
chmod 600 Gateway/keys.json
```

Change `ids` to the seal IDs you will use. When adding a seal to an existing
installation, preserve the current key for each existing seal and add a new
entry with fresh random values; do not regenerate keys for seals already in
service unless you also reprovision their firmware. The gateway checks that
each AES key and nonce prefix contain 32 and 18 hexadecimal characters,
respectively. On POSIX systems it also refuses a key file readable by group or
other users. Copy each seal's matching values into that seal's `secrets.h` in
the byte-array format shown in `secrets.example.h`, and set its `SEAL_ID` to
the corresponding ID. The old top-level single-key `keys.json` format remains
supported as seal 1.

When migrating an existing one-seal file, move its current values under ID 1
and add one entry per new seal. The resulting structure looks like this
(replace the labels with the actual hex strings):

```json
{
  "seals": {
    "1": {
      "SMARTSEAL_AES_KEY": "existing 32-character key",
      "SMARTSEAL_NONCE_PREFIX": "existing 18-character prefix"
    },
    "2": {
      "SMARTSEAL_AES_KEY": "new 32-character key",
      "SMARTSEAL_NONCE_PREFIX": "new 18-character prefix"
    }
  }
}
```

The repository ignores local key files. For a production seal's first
provisioning, hold D6 while powering it on to initialize sequence storage. On
normal restarts, do not hold D6; the stored sequence continues automatically.
If sequence storage is missing or corrupted, create a new AES key and nonce
prefix, update both sides, then hold D6 during boot. The sensorless test
transmitter has no button; use its build-time provisioning setting described
below. If sequence storage is lost or corrupted, rotate its key and prefix on
both sides before reprovisioning.

## Build and upload the seal firmware

1. Copy `XIAOnRF8540/SmartSeal_Encrypted/secrets.example.h` to
   `XIAOnRF8540/SmartSeal_Encrypted/secrets.h`.
2. For each physical seal, use a unique `SEAL_ID` and enter the AES key and
   nonce prefix assigned to that ID in `Gateway/keys.json`. Build and upload a
   separate firmware image for each seal ID.
3. Open `XIAOnRF8540/SmartSeal_Encrypted/SmartSeal_Encrypted.ino` in Arduino
   IDE, select the Seeed XIAO nRF52840 Sense board and its serial port, then
   build and upload.
4. Open Serial Monitor at 115200 baud. The firmware initializes the ADXL345,
   CryptoCell, persistent sequence storage, and BLE advertising.
5. Press D6 to start or stop recording. On start, the firmware calibrates the
   vibration sensor; keep the seal still during calibration.

The firmware reads temperature from A0 and vibration from A2. It samples the
ADXL345 over I2C at 100 Hz. The main loop runs at about 100 Hz and updates the
advertisement every 5 seconds while recording. Vibration is detected from ADC
deviation from a calibrated baseline; movement is detected from changes in the
accelerometer readings. The current encrypted sketch has no separate tamper
sensor, so its `tamper` field is always false. Vibration and movement are
reported separately.

## Build the sensorless test transmitter

Use a spare XIAO nRF52840 to simulate another seal without connecting sensors
or other components. The sketch broadcasts authenticated packets immediately
and cycles through synthetic temperature, tamper, vibration, and movement
values every five seconds.

1. Copy `XIAOnRF8540/Encrypted_Test_Transmitter/secrets.example.h` to
   `XIAOnRF8540/Encrypted_Test_Transmitter/secrets.h`. The example uses test
   seal ID `2`; leave the production seal on ID `1`.
2. Generate a fresh AES key and nonce prefix for ID 2. Add them under `"2"` in
   `Gateway/keys.json`, and copy the same values into the test transmitter's
   `secrets.h`. Do not reuse seal 1's key or prefix.
3. Set `ALLOW_SEQUENCE_PROVISIONING` to `1` in `secrets.h` for the first
   boot. Open
   `XIAOnRF8540/Encrypted_Test_Transmitter/Encrypted_Test_Transmitter.ino` in
   Arduino IDE, select the XIAO nRF52840 board and its serial port, then build
   and upload.
4. Open Serial Monitor at 115200 baud and wait for the sequence storage
   initialization message.
5. Set `ALLOW_SEQUENCE_PROVISIONING` back to `0` and upload again without
   erasing the board's internal filesystem. The transmitter now starts
   advertising and will fail closed if sequence storage is later lost or
   corrupted. No button or jumper is needed.
6. If storage is ever lost or corrupted, install a new key and nonce prefix in
   both transmitter and gateway, temporarily enable provisioning, and repeat
   these steps.

Set `SEAL_ID` and matching key material in each transmitter's own
`secrets.h`. When seal 1 and seal 2 are both configured in `Gateway/keys.json`
and advertising, one BLE scan window can collect the latest valid packet from
each seal. The gateway processes all collected packets and stores sequence
state independently by seal ID. The gateway supports IDs 1 through 255.

## Encrypted advertisement format

The BLE manufacturer data contains the 2-byte company ID `0x5353` followed by
a 21-byte packet:

| Packet bytes | Contents |
|---|---|
| 0 | Magic value `0xA5` |
| 1 | Protocol version `3` |
| 2 | Seal ID, configured per seal (`1`–`255`) |
| 3–6 | 32-bit little-endian sequence number |
| 7–12 | AES-128-CCM ciphertext |
| 13–20 | 8-byte authentication tag |

The nonce is the 9-byte configured prefix followed by the 4 transmitted
sequence bytes. The first 7 packet bytes are authenticated as additional data.
The encrypted plaintext contains signed temperature in tenths of a degree C,
a tamper byte, vibration in hundredths of a volt, and a movement type.

The firmware stores its sequence counter in internal flash and reserves ranges
before using them so a normal restart does not reuse a nonce. The gateway
stores event and seal status in `Gateway/smartseal.db`. Preserve that database
when restarting the gateway.

## Run the gateway on the Raspberry Pi

From the repository root, start the gateway with real BLE scanning and local
Ollama analysis:

```bash
export SMARTSEAL_SIMULATION=0
export SMARTSEAL_AI_PROVIDER=ollama
python3 Gateway/XIAO/gateway_main.py
```

Ollama must be running on the Pi with the configured vision model available.
The default model is `moondream`.

Press D6 on the seal to start recording, then wait for an advertisement. If no
packet arrives, check that Bluetooth is enabled, the adapter is available to
the account running Python, and the seal has the matching encrypted firmware
and keys. During each scan window, the gateway collects one latest valid
packet per configured seal ID and processes every collected seal packet; it no
longer selects just one seal when multiple seals are advertising nearby.

## Run the dashboard

Create an account from the repository root:

```bash
python3 -m Dashboard.manage_accounts add seal-admin
```

The command prompts for a password of at least 12 characters. The password is
stored as a hash in the local database. There is no public registration; run
the command again to add another account.

In a separate terminal, start the dashboard:

```bash
python3 Dashboard/dashboard.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Visitors can view the
dashboard, events, archives, and captured images without signing in. Sign in
to enable archive deletion. The server listens on localhost by default.
Select **Show temperature graph** to view readings over time. The graph can
show all seal IDs or one selected seal, follows the selected live/archive event
history, and marks the 2 °C and 8 °C limits.

The dashboard creates `Gateway/.dashboard_secret` for persistent login
sessions. The file is hidden on Linux and ignored by Git. Keep it private.

When stopped with Ctrl+C, the gateway writes stored events to a timestamped CSV
in `Gateway/archives/`. Deleting a saved archive removes its CSV. Captured
images are removed only when no live event or remaining archive references
them.

Events and archived CSV rows expire 90 days after their event timestamp.
Captured images are deleted once no remaining event or archive references
them. Cleanup runs when the gateway or dashboard initializes, and periodically
while the dashboard is receiving requests.

Temperature alerts below 2 °C or above 8 °C do not by themselves trigger a
photo; vibration or movement events trigger capture and optional image
analysis.

## Simulation without BLE hardware

Simulation generates packets in memory, so it can be used on a development
computer without the XIAO or a BLE adapter. The gateway still loads
`Gateway/keys.json` during startup, so create that file first as described
above. Simulation does not check packets against firmware encryption.

PowerShell:

```powershell
$env:SMARTSEAL_SIMULATION = "1"
$env:SMARTSEAL_AI_PROVIDER = "none"
python3 Gateway/XIAO/gateway_main.py
```

To use real BLE hardware and Ollama again in PowerShell:

```powershell
$env:SMARTSEAL_SIMULATION = "0"
$env:SMARTSEAL_AI_PROVIDER = "ollama"
python3 Gateway/XIAO/gateway_main.py
```

The simulator starts its sequence counter at 1 each time it starts. Since the
gateway stores sequence state, use a separate disposable checkout or database
when repeating simulation runs. Do not delete a database containing real
events just to reset a simulation.

## Optional local image analysis

The gateway uses Ollama locally when it captures an image. Install and run
Ollama on the Pi with a vision model such as `moondream`. The gateway accepts
only loopback Ollama URLs. To use sensor-only fallback text, set
`SMARTSEAL_AI_PROVIDER=none`. The active analyzer does not use OpenAI or send
images to an external AI provider.

## Syntax check

From the repository root:

```bash
python3 -m compileall -q Gateway Dashboard
```

## Main paths

```text
XIAOnRF8540/SmartSeal_Encrypted/   Encrypted BLE seal firmware
XIAOnRF8540/Encrypted_Test_Transmitter/ Sensorless encrypted BLE test sender
Gateway/ble_scanner.py             Advertisement decryption and validation
Gateway/XIAO/                      XIAO advertisement gateway entry point
Gateway/gateway_main.py            Event handling
Gateway/database.py                SQLite storage, retention, and CSV archives
Dashboard/                         Flask dashboard and account management
Gateway/keys.json                  Local gateway secrets (ignored by Git)
```
