# SmartSeal+

SmartSeal+ monitors a shipment seal using a Seeed XIAO nRF52840 Sense. The
seal samples temperature, vibration, and movement, then broadcasts an
authenticated, encrypted BLE manufacturer advertisement. A Python gateway
receives the advertisement, records events in SQLite, and serves a Flask
dashboard.

This guide covers the encrypted seal firmware in
`XIAOnRF8540/SmartSeal_Encrypted/` and its BLE advertising gateway. The
firmware is configured for seal ID `1`.

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

The gateway reads `Gateway/keys.json`. The firmware reads
`XIAOnRF8540/SmartSeal_Encrypted/secrets.h`. The AES key and nonce prefix in
these files must match exactly. Do not use the all-zero example values, commit
either secret file, or reuse the pair for another seal.

Generate a random 128-bit AES key and 9-byte nonce prefix for the gateway:

```bash
python3 -c 'import json,secrets; from pathlib import Path; Path("Gateway/keys.json").write_text(json.dumps({"SMARTSEAL_AES_KEY":secrets.token_hex(16),"SMARTSEAL_NONCE_PREFIX":secrets.token_hex(9)},indent=2),encoding="utf-8")'
chmod 600 Gateway/keys.json
```

The gateway checks that these fields contain 32 and 18 hexadecimal characters,
respectively. On POSIX systems it also refuses a key file readable by group or
other users. Copy the same key and prefix into `secrets.h` in the byte-array
format shown in `secrets.example.h`, and keep `SEAL_ID` set to `1`.

The repository ignores both secret files. If the firmware reports corrupted
sequence storage, do not reset its sequence and keep using the same key. Create
a new key and nonce prefix, update both sides, and provision the firmware
again.

## Build and upload the seal firmware

1. Copy `XIAOnRF8540/SmartSeal_Encrypted/secrets.example.h` to
   `XIAOnRF8540/SmartSeal_Encrypted/secrets.h`.
2. Set `SEAL_ID` to `1` and enter the same `AES_KEY` and `NONCE_PREFIX` values
   used in `Gateway/keys.json`.
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

## Encrypted advertisement format

The BLE manufacturer data contains the 2-byte company ID `0x5353` followed by
a 21-byte packet:

| Packet bytes | Contents |
|---|---|
| 0 | Magic value `0xA5` |
| 1 | Protocol version `3` |
| 2 | Seal ID, currently `1` |
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
and keys.

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
Ollama on the Pi with a vision model such as `moondream`. To use sensor-only
fallback text, set `SMARTSEAL_AI_PROVIDER=none`. The active analyzer does not
use OpenAI or send images to an external AI provider.

## Syntax check

From the repository root:

```bash
python3 -m compileall -q Gateway Dashboard
```

## Main paths

```text
XIAOnRF8540/SmartSeal_Encrypted/   Encrypted BLE seal firmware
Gateway/ble_scanner.py             Advertisement decryption and validation
Gateway/XIAO/                      XIAO advertisement gateway entry point
Gateway/gateway_main.py            Event handling
Gateway/database.py                SQLite storage, retention, and CSV archives
Dashboard/                         Flask dashboard and account management
Gateway/keys.json                  Local gateway secrets (ignored by Git)
```
