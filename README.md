# SmartSeal+

SmartSeal+ monitors one shipment seal with a Seeed XIAO nRF52840 Sense. The
seal firmware samples temperature, vibration, and movement, then broadcasts an
authenticated, encrypted BLE manufacturer advertisement. A Python gateway
receives the advertisement, records events in SQLite, and serves a local Flask
dashboard.

This guide documents the encrypted seal firmware in
`XIAOnRF8540/SmartSeal_Encrypted/` and its BLE advertising gateway. The
firmware and gateway are configured for seal ID `1`.

## System overview

```text
XIAO nRF52840 Sense
  └─ AES-128-CCM BLE manufacturer advertisement (company ID 0x5353)
       └─ Gateway/XIAO/ble_scanner.py
            └─ Gateway/gateway_main.py → SQLite → Flask dashboard
```

The advertisement protects sensor contents and authenticates the packet. The
seal ID and sequence number remain visible and are authenticated as part of
the packet header. The gateway rejects invalid tags, seal IDs other than 1,
and stale or replayed sequence numbers. Encryption does not hide the seal's
presence or prevent radio jamming.

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

On Raspberry Pi OS, the system packages are:

```bash
sudo apt update
sudo apt install python3-bleak python3-flask python3-pil python3-cryptography
```

On Windows, macOS, or another Linux host, install the Python dependencies in a
virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

In PowerShell, activate the environment with:

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
a new key and nonce prefix, update both sides, and provision the firmware again.

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
deviation from a calibrated baseline; movement is detected from changes in
the accelerometer readings. The current encrypted sketch has no separate
tamper sensor, so its `tamper` field is always false. Vibration and movement
are reported separately.

## Encrypted advertisement format

The BLE manufacturer data contains the 2-byte company ID `0x5353` followed by
a 21-byte packet:

| Packet bytes | Contents |
|---|---|
| 0 | Magic value `0xA5` |
| 1 | Protocol version `3` |
| 2 | Seal ID, currently `1` |
| 3–6 | 32-bit little-endian event sequence |
| 7–12 | AES-128-CCM ciphertext |
| 13–20 | 8-byte authentication tag |

The nonce is the 9-byte configured prefix followed by the 4 transmitted
sequence bytes. The first 7 packet bytes are authenticated as additional data.
The encrypted plaintext contains signed temperature in tenths of a degree C,
a tamper byte, vibration in hundredths of a volt, and a movement type.

The firmware stores its sequence counter in internal flash and reserves ranges
before using them so a normal restart does not reuse a nonce. The gateway
stores the highest accepted sequence in `Gateway/smartseal.db`; deleting or
restoring an older database also resets the gateway's replay protection state.

## Run the gateway and dashboard

Start the advertisement gateway from the repository root:

```bash
python3 Gateway/XIAO/gateway_main.py
```

In PowerShell:

```powershell
python Gateway/XIAO/gateway_main.py
```

The gateway scans for up to 5 seconds per attempt. Press D6 on the seal to
start recording, then wait for an advertisement. If no packet arrives, check
that Bluetooth is enabled, the adapter is available to the account running
Python, and the seal has the matching encrypted firmware and keys.

In a separate terminal, run the dashboard:

```bash
python3 Dashboard/dashboard.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The dashboard shows live
events and saved archives. It runs on localhost with Flask debug mode disabled.

When stopped with Ctrl+C, the gateway writes stored events to a timestamped
CSV in `Gateway/archives/`. Captured images are stored in `Gateway/images/`.
Temperature alerts below 2 °C or above 8 °C do not by themselves trigger a
photo; vibration or movement events trigger capture and optional image
analysis.

## Simulation without BLE hardware

Simulation generates packets in memory, so it can be used on a development
computer without the XIAO or a BLE adapter. The gateway still loads
`Gateway/keys.json` during startup, so create that file first as described
above. Simulation does not check packets against firmware encryption.

In PowerShell:

```powershell
$env:SMARTSEAL_SIMULATION = "1"
$env:SMARTSEAL_AI_PROVIDER = "none"
python3 Gateway/XIAO/gateway_main.py
```
To revert this setting use:
```powershell
$env:SMARTSEAL_SIMULATION = "0"
$env:SMARTSEAL_AI_PROVIDER = "ollama"
python3 Gateway/XIAO/gateway_main.py
```
The simulator starts its sequence counter at 1 each time it starts. Since the
gateway persists replay state, use a separate disposable checkout or database
when repeating simulation runs; do not delete a database containing real
events just to reset a simulation.

## Optional image analysis

The gateway uses local Ollama image analysis by default when it captures an
image. To use sensor-only fallback text instead, set
`SMARTSEAL_AI_PROVIDER=none`. To use the existing OpenAI integration, set
`SMARTSEAL_AI_PROVIDER=openai` and `OPENAI_API_KEY` in the gateway environment.
Images sent to OpenAI are sent to the configured external service.

## Checks

Check Python syntax from the repository root with:

```bash
python3 -m compileall -q Gateway Dashboard
```

Some existing test files still target older plaintext or multi-seal packet
behavior. They are not a reliable verification suite for the encrypted
version-3, seal-ID-1 workflow until those tests are updated.

## Main paths in this guide

```text
XIAOnRF8540/SmartSeal_Encrypted/   Encrypted BLE seal firmware
Gateway/ble_scanner.py             Advertisement decryption and validation
Gateway/XIAO/                      XIAO advertisement gateway entry point
Gateway/gateway_main.py            Event handling and replay protection
Gateway/database.py                SQLite storage and CSV archives
Dashboard/                         Local Flask dashboard
Gateway/keys.json                  Local gateway secrets (ignored by Git)
```