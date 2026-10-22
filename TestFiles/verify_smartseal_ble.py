#The purpose of this file is to verify the BLE advertising of the SmartSeal+ device by scanning for it and displaying its information.
#Run the following command to execute this script:
#cd ~/SmartSealPlus/TestFiles
#python3 verify_smartseal_ble.py


import asyncio
from bleak import BleakScanner

TARGET_NAME = "SmartSeal-01"
MANUFACTURER_ID = 0x5353

async def main():
    print(f"Waiting for messages from {TARGET_NAME}...")
    print("Press Ctrl+C to stop.\n")

    last_message = None

    while True:
        devices = await BleakScanner.discover(
            timeout=3,
            return_adv=True
        )

        for address, (device, adv) in devices.items():
            name = adv.local_name or device.name or ""

            if name != TARGET_NAME:
                continue

            for company_id, data in adv.manufacturer_data.items():
                if company_id != MANUFACTURER_ID:
                    continue

                message = data.decode("utf-8", errors="replace").strip()

                # Only print when a new message is received
                if message != last_message:
                    print(f"[{name}] {message}")
                    last_message = message

asyncio.run(main())
