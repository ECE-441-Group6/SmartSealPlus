# ============================================================
# SmartSealPlus - ESP32 BLE Vibration Recorder
#
# Receives:
#   START
#   STOP
#   D,timestamp_ms,adc_value,button2_state
#
# Saves recorded samples to CSV files.
# Includes BLE connection retries and automatic reconnection.
# ============================================================

import asyncio
import csv
from datetime import datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner


# ============================================================
# BLE CONFIGURATION
# ============================================================

DEVICE_NAME = "ESP32_Recorder"

SERVICE_UUID = "12345678-1234-1234-1234-1234567890ab"

CHARACTERISTIC_UUID = "12345678-1234-1234-1234-1234567890ac"

SCAN_TIMEOUT = 20.0
CONNECT_TIMEOUT = 30.0
RECONNECT_DELAY = 3.0


# ============================================================
# CSV CONFIGURATION
# ============================================================

OUTPUT_DIR = Path.home() / "esp32_recordings"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# RECORDING STATE
# ============================================================

csv_file = None
csv_writer = None
current_file_path = None
recording = False


# ============================================================
# START RECORDING
# ============================================================

def start_recording():
    global csv_file, csv_writer
    global current_file_path, recording

    # Avoid accidentally leaving an existing file open.
    if recording:
        stop_recording()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"recording_{timestamp}.csv"
    current_file_path = OUTPUT_DIR / filename

    try:
        csv_file = open(
            current_file_path,
            "w",
            newline="",
            buffering=1,
            encoding="utf-8",
        )

        csv_writer = csv.writer(csv_file)

        csv_writer.writerow([
            "timestamp_ms",
            "adc_value",
            "button2_state",
        ])

        csv_file.flush()
        recording = True

        print(f"\nRecording started: {current_file_path}")

    except OSError as error:
        print(f"Could not create CSV file: {error}")

        if csv_file is not None:
            try:
                csv_file.close()
            except OSError:
                pass

        csv_file = None
        csv_writer = None
        current_file_path = None
        recording = False


# ============================================================
# STOP RECORDING
# ============================================================

def stop_recording():
    global csv_file, csv_writer
    global current_file_path, recording

    if not recording and csv_file is None:
        return

    saved_path = current_file_path

    # Reset state even if flushing or closing fails.
    file_to_close = csv_file

    csv_file = None
    csv_writer = None
    current_file_path = None
    recording = False

    if file_to_close is not None:
        try:
            file_to_close.flush()
            file_to_close.close()
        except OSError as error:
            print(f"Error closing CSV file: {error}")

    if saved_path is not None:
        print(f"Recording saved: {saved_path}")


# ============================================================
# BLE NOTIFICATION HANDLER
# ============================================================

def notification_handler(sender, data: bytearray):
    global recording, csv_file, csv_writer

    try:
        message = data.decode("utf-8").strip()

        # --------------------------------------------
        # START COMMAND
        # --------------------------------------------

        if message == "START":
            start_recording()
            return

        # --------------------------------------------
        # STOP COMMAND
        # --------------------------------------------

        if message == "STOP":
            stop_recording()
            return

        # --------------------------------------------
        # DATA PACKET
        # Format: D,timestamp_ms,adc_value,button2_state
        # --------------------------------------------

        if not message.startswith("D,"):
            print(f"Unknown BLE message: {message!r}")
            return

        if not recording or csv_writer is None or csv_file is None:
            return

        parts = message.split(",")

        if len(parts) != 4:
            print(f"Invalid packet format: {message!r}")
            return

        _, timestamp_ms, adc_value, button2_state = parts

        timestamp_ms = int(timestamp_ms)
        adc_value = int(adc_value)
        button2_state = int(button2_state)

        if timestamp_ms < 0:
            print(f"Invalid timestamp: {timestamp_ms}")
            return

        if not 0 <= adc_value <= 4095:
            print(f"Invalid ADC value: {adc_value}")
            return

        if button2_state not in (0, 1):
            print(f"Invalid Button 2 state: {button2_state}")
            return

        csv_writer.writerow([
            timestamp_ms,
            adc_value,
            button2_state,
        ])

        # Flush so recent samples are written to the file.
        csv_file.flush()

    except (UnicodeDecodeError, ValueError) as error:
        print(f"Invalid BLE notification: {error}")

    except OSError as error:
        print(f"CSV write error: {error}")
        stop_recording()


# ============================================================
# FIND ESP32
# ============================================================

async def find_esp32():
    print(f"\nSearching for {DEVICE_NAME}...")

    device = await BleakScanner.find_device_by_filter(
        lambda device, advertisement: (
            device.name == DEVICE_NAME
            or advertisement.local_name == DEVICE_NAME
        ),
        timeout=SCAN_TIMEOUT,
    )

    if device is None:
        print(f"Could not find {DEVICE_NAME}.")
        print("Check ESP32 power and BLE advertising.")
        return None

    print(f"Found device: {device.name}")
    print(f"Bluetooth address: {device.address}")

    return device


# ============================================================
# CONNECT AND RECEIVE NOTIFICATIONS
# ============================================================

async def connect_and_receive(device):
    print("Connecting to ESP32...")

    async with BleakClient(
        device,
        timeout=CONNECT_TIMEOUT,
    ) as client:

        if not client.is_connected:
            raise ConnectionError("BLE connection was not established")

        print("Connected to ESP32 successfully!")

        # Verify the expected characteristic exists.
        characteristic = None

        for service in client.services:
            if service.uuid.lower() == SERVICE_UUID.lower():
                for char in service.characteristics:
                    if char.uuid.lower() == CHARACTERISTIC_UUID.lower():
                        characteristic = char
                        break

        if characteristic is None:
            raise RuntimeError(
                "Expected BLE characteristic not found. "
                "Check the ESP32 service and characteristic UUIDs."
            )

        if "notify" not in characteristic.properties:
            raise RuntimeError(
                "The ESP32 characteristic does not support notifications."
            )

        await client.start_notify(
            characteristic,
            notification_handler,
        )

        print("BLE notifications enabled.")
        print("Press ESP32 Button 1 to start or stop recording.")
        print("Press Ctrl+C to exit.")

        # Wait while the BLE connection remains active.
        while client.is_connected:
            await asyncio.sleep(0.5)

        print("BLE connection lost.")

    # Save and close any active recording after disconnect.
    stop_recording()


# ============================================================
# MAIN RECONNECTION LOOP
# ============================================================

async def scan_ble():
    print("SmartSealPlus BLE Gateway starting...")

    while True:
        try:
            device = await find_esp32()

            if device is None:
                print(f"Retrying scan in {RECONNECT_DELAY:.0f} seconds...")
                await asyncio.sleep(RECONNECT_DELAY)
                continue

            await connect_and_receive(device)

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(
                f"BLE error: {type(error).__name__}: {error}"
            )

            stop_recording()

        print(f"Retrying BLE connection in {RECONNECT_DELAY:.0f} seconds...")
        await asyncio.sleep(RECONNECT_DELAY)


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(scan_ble())

    except KeyboardInterrupt:
        print("\nProgram stopped by user.")

    finally:
        stop_recording()
        print("Gateway shutdown complete.")