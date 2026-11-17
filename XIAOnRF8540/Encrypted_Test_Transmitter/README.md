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
5. On first boot only, hold D6 low while powering/resetting the board to
   initialize its persistent sequence counter. Use a temporary D6-to-GND
   jumper; no sensor hardware is needed. Do not repeat provisioning with the
   same key after sequence storage has been erased.
6. Open Serial Monitor at 115200 baud. Packets start broadcasting immediately.

The sequence counter is persisted with the same two-slot flash scheme as the
seal firmware. Normal restarts continue safely without reusing an AES-CCM
nonce. If sequence storage is lost, create a new test key and nonce prefix and
update both the transmitter and receiver before sending again.

## Multiple test transmitters

The advertising gateway accepts IDs `1` through `255` when each ID has a
matching key and nonce prefix in `Gateway/keys.json`. For each physical test
XIAO, assign a different ID, AES key, and nonce prefix, then build the sketch
with those values in its local `secrets.h`. The gateway stores event sequence
state independently for each ID. Never share the same key and nonce prefix
between transmitters because their persistent sequence counters are separate.
