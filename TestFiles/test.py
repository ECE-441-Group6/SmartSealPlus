# Tests event handling for the SmartSealPlus gateway. Raspberry Pi BLE-to-camera trigger
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from bleak import BleakScanner

TARGET_NAME = "SmartSeal-01"
TEST_COMPANY_ID = 0xFFFF

ALERTS = {"TAMPER1", "TEMPHIGH", "TEMPLOW"}

EVENT_DIR = Path.home() / "SmartSealPlus" / "events"
EVENT_DIR.mkdir(parents=True, exist_ok=True)

last_status = None


def capture_image(status):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = EVENT_DIR / f"{timestamp}_{status}.jpg"

    print(f"ALERT: {status}")
    print("Activating Raspberry Pi camera...")

    try:
        subprocess.run(
            [
                "rpicam-still",
                "-n",
                "-t", "1000",
                "-o", str(filename)
            ],
            check=True,
            timeout=15
        )

        print(f"Photo saved: {filename}\n")

    except (subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError) as error:
        print(f"Camera capture failed: {error}")


async def main():
    global last_status

    print(f"Listening for {TARGET_NAME}...")
    print(f"Event photos will be saved in: {EVENT_DIR}")
    print("Press Ctrl+C to stop.\n")

    while True:
        devices = await BleakScanner.discover(
            timeout=2,
            return_adv=True
        )

        for address, (device, adv) in devices.items():
            name = adv.local_name or device.name or ""

            if name != TARGET_NAME:
                continue

            for company_id, data in adv.manufacturer_data.items():
                if company_id != TEST_COMPANY_ID:
                    continue

                status = data.decode(
                    "utf-8", errors="replace"
                ).strip("\x00 \r\n")

                if status == last_status:
                    continue

                last_status = status
                print(f"[{name}] Status: {status}")

                if status in ALERTS:
                    # Capture one photo for each new alert status.
                    await asyncio.to_thread(
                        capture_image, status
                    )

                elif status == "NORMAL":
                    print("System is back to normal.\n")


try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nGateway stopped.")
