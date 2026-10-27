
import asyncio
import csv
import struct
from datetime import datetime, timezone

from bleak import BleakClient, BleakScanner

DEVICE_NAME = "Xiao_Recorder"

SERVICE_UUID = "12345678-1234-1234-1234-1234567890ab"
CHAR_UUID = "12345678-1234-1234-1234-1234567890ac"

OUTPUT_FILE = "accelerometer_log.csv"

# uint32 timestamp + three int16 milli-g values
PACKET_FORMAT = "<Ihhh"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)


async def main():
    print(f"Searching for {DEVICE_NAME}...")

    device = await BleakScanner.find_device_by_name(
        DEVICE_NAME,
        timeout=20.0
    )

    if device is None:
        print("Device not found. Check power and BLE advertising.")
        return

    print(f"Found {device.name}: {device.address}")

    with open(OUTPUT_FILE, "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "host_time_utc",
            "device_timestamp_ms",
            "ax_g",
            "ay_g",
            "az_g"
        ])

        loop = asyncio.get_running_loop()
        last_flush = loop.time()
        sample_count = 0

        async with BleakClient(device) as client:
            print("Connected:", client.is_connected)
            print("Recording. Press Ctrl+C to stop.")

            def handle_notification(sender, data):
                nonlocal sample_count, last_flush

                if len(data) != PACKET_SIZE:
                    print(f"Unexpected packet length: {len(data)}")
                    return

                timestamp, ax_mg, ay_mg, az_mg = struct.unpack(
                    PACKET_FORMAT,
                    data
                )

                # Convert milli-g to g
                ax = ax_mg / 1000.0
                ay = ay_mg / 1000.0
                az = az_mg / 1000.0

                host_time = datetime.now(timezone.utc).isoformat()

                writer.writerow([
                    host_time,
                    timestamp,
                    ax,
                    ay,
                    az
                ])

                sample_count += 1

                # Flush periodically to protect recorded data
                now = loop.time()

                if now - last_flush >= 1.0:
                    file.flush()
                    last_flush = now

                if sample_count % 50 == 0:
                    print(
                        f"Samples: {sample_count} | "
                        f"X={ax:+.3f} g | "
                        f"Y={ay:+.3f} g | "
                        f"Z={az:+.3f} g"
                    )

            await client.start_notify(
                CHAR_UUID,
                handle_notification
            )

            try:
                while client.is_connected:
                    await asyncio.sleep(1)

            finally:
                if client.is_connected:
                    await client.stop_notify(CHAR_UUID)

        file.flush()

    print(f"Saved {sample_count} samples to {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nRecording stopped.")
