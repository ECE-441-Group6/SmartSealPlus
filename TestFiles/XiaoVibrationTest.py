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

OUTPUT_DIR = Path.home() / "xiao_recordings"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# RECORDING STATE
# ============================================================

csv_file = None
csv_writer = None
current_file_path = None
recording = False


# ============================================================
# START A NEW CSV FILE
# ============================================================

def start_recording():
    global csv_file, csv_writer
    global current_file_path, recording

    # Avoid leaving an earlier file open
    if recording:
        stop_recording()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"recording_{timestamp}.csv"

    current_file_path = OUTPUT_DIR / filename

    csv_file = open(
        current_file_path,
        mode="w",
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


# ============================================================
# CLOSE AND SAVE THE CURRENT CSV
# ============================================================

def stop_recording():
    global csv_file, csv_writer
    global current_file_path, recording

    if not recording:
        return

    path = current_file_path

    csv_file.flush()
    csv_file.close()

    print(f"Recording saved: {path}")

    csv_file = None
    csv_writer = None
    current_file_path = None
    recording = False


# ============================================================
# PROCESS BLE NOTIFICATIONS
# ============================================================

def notification_handler(sender, data: bytearray):
    global recording

    try:
        message = data.decode("utf-8").strip()

        # START: create a new CSV
        if message == "START":
            start_recording()
            return

        # STOP: close the current CSV
        if message == "STOP":
            stop_recording()
            return

        # Sensor data format:
        # D,timestamp_ms,adc_value,button2_state
        if message.startswith("D,"):

            if not recording or csv_writer is None:
                return

            parts = message.split(",")

            if len(parts) != 4:
                print(f"Invalid packet: {message!r}")
                return

            _, timestamp_ms, adc_value, button2_state = parts

            timestamp_ms = int(timestamp_ms)
            adc_value = int(adc_value)
            button2_state = int(button2_state)

            # Validate data
            if timestamp_ms < 0:
                return

            if not 0 <= adc_value <= 4095:
                print(f"Invalid ADC value: {adc_value}")
                return

            if button2_state not in (0, 1):
                print(f"Invalid Button 2 state: {button2_state}")
                return

            # Write one sample to the CSV
            csv_writer.writerow([
                timestamp_ms,
                adc_value,
                button2_state,
            ])

            # Flush so recent samples are written to disk
            csv_file.flush()

    except (UnicodeDecodeError, ValueError) as error:
        print(f"Invalid notification: {error}")


# ============================================================
# CONNECT TO THE XIAO
# ============================================================

async def main():
    print(f"Searching for {DEVICE_NAME}...")

    device = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name == DEVICE_NAME,
        timeout=20.0,
    )

    if device is None:
        print("Device not found.")
        print("Check that the XIAO is powered and advertising.")
        return

    print(f"Found: {device.name}")
    print("Connecting...")

    try:
        async with BleakClient(device) as client:
            print("Connected to XIAO nRF52840.")
            print("Waiting for Button 1...")
            print("Press Ctrl+C to exit.")

            await client.start_notify(
                CHARACTERISTIC_UUID,
                notification_handler,
            )

            while True:
                await asyncio.sleep(1)

    finally:
        # Save any recording that remains open
        stop_recording()


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\nProgram stopped.")

    finally:
        stop_recording()