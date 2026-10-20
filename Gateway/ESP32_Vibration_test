# Reads BLE notifications from the ESP32 SmartSeal recorder.
# Receives START, STOP, and D,timestamp_ms,adc_value,button2_state packets.
# Saves recorded data to CSV files.

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


def start_recording():
    global csv_file, csv_writer
    global current_file_path, recording

    if recording:
        stop_recording()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"recording_{timestamp}.csv"
    current_file_path = OUTPUT_DIR / filename

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


def stop_recording():
    global csv_file, csv_writer
    global current_file_path, recording

    if not recording:
        return

    saved_path = current_file_path

    if csv_file is not None:
        csv_file.flush()
        csv_file.close()

    print(f"Recording saved: {saved_path}")

    csv_file = None
    csv_writer = None
    current_file_path = None
    recording = False


def notification_handler(sender, data: bytearray):
    global recording

    try:
        message = data.decode("utf-8").strip()

        if message == "START":
            start_recording()
            return

        if message == "STOP":
            stop_recording()
            return

        if message.startswith("D,"):
            if not recording or csv_writer is None:
                return

            parts = message.split(",")

            if len(parts) != 4:
                print(f"Invalid packet: {message}")
                return

            _, timestamp_ms, adc_value, button2_state = parts

            timestamp_ms = int(timestamp_ms)
            adc_value = int(adc_value)
            button2_state = int(button2_state)

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

            csv_file.flush()

    except (UnicodeDecodeError, ValueError) as error:
        print(f"Invalid notification: {error}")


async def scan_ble():
    """Find the ESP32 recorder, connect, and receive BLE notifications."""

    print("Searching for ESP32 BLE device...")

    device = await BleakScanner.find_device_by_filter(
        lambda d, ad: (
            d.name == DEVICE_NAME
            or ad.local_name == DEVICE_NAME
        ),
        timeout=20.0,
    )

    if device is None:
        print(f"Could not find {DEVICE_NAME}.")
        print("Check that the ESP32 is powered and advertising.")
        return

    print(f"Found device: {device.name}")
    print("Connecting...")

    try:
        async with BleakClient(device) as client:
            print("Connected to ESP32.")
            print("Waiting for recording button...")
            print("Press Ctrl+C to exit.")

            await client.start_notify(
                CHARACTERISTIC_UUID,
                notification_handler,
            )

            while True:
                await asyncio.sleep(1)

    finally:
        stop_recording()


# Allow this file to run independently for testing.
if __name__ == "__main__":
    try:
        asyncio.run(scan_ble())
    except KeyboardInterrupt:
        print("\nProgram stopped.")
    finally:
        stop_recording()