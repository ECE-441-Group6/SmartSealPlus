# Sensorless encrypted BLE test transmitter

This sketch turns a spare XIAO nRF52840 into a sensorless SmartSeal packet
source. It broadcasts encrypted manufacturer advertisements using the same
packet format as `SmartSeal_Encrypted`, and rotates through four synthetic
temperature, tamper, vibration, and movement samples every five seconds.
No sensors, buzzer, or accelerometer need to be connected.

## Build and provision

1. Copy `secrets.example.h` to `secrets.h` in this folder. Its example uses
   test seal ID `2` so it won't collide with a default production seal ID `1`.
2. Generate a dedicated test AES key and nonce prefix. Do not copy the key and
   prefix from a production seal: each XIAO has its own sequence counter, and
   two transmitters using the same key/prefix can reuse AES-CCM nonces.
3. Add a matching entry for this test seal ID to the `"seals"` object in
   `Gateway/keys.json`. Stop production seals only if the test transmitter is
   configured with a production ID; preferably assign it a separate test ID.
4. Open `Encrypted_Test_Transmitter.ino` in Arduino IDE, select the Seeed XIAO
   nRF52840 board, and upload.
5. Open Serial Monitor at 115200 baud. The first boot initializes its blank
   sequence storage automatically, and packets start broadcasting immediately.

The sequence counter is persisted with the same two-slot flash scheme as the
seal firmware. Normal restarts continue safely without reusing an AES-CCM
nonce. If sequence storage is erased or corrupted, install a new test key and
nonce prefix in both the transmitter and gateway before powering the
transmitter back on. It will then reinitialize its sequence counter
automatically.

## Multiple test transmitters

The advertising gateway accepts IDs `1` through `255` when each ID has a
matching key and nonce prefix in `Gateway/keys.json`. For each physical test
XIAO, assign a different ID, AES key, and nonce prefix, then build the sketch
with those values in its local `secrets.h`. The gateway stores event sequence
state independently for each ID. Never share the same key and nonce prefix
between transmitters because their persistent sequence counters are separate.
