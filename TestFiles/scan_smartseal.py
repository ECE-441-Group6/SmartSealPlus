#The purpose of this file is to scan for the SmartSeal+ BLE device and display its information.
#Run the following command to execute this script:
#cd ~/SmartSealPlus/TestFiles
#~/ble-venv/bin/python scan_smartseal.py

import asyncio
from bleak import BleakScanner

TARGET_NAME = "SmartSeal-01"

async def main():
    print(f"Scanning for {TARGET_NAME}...")

    while True:
        devices = await BleakScanner.discover(
            timeout=5,
            return_adv=True
        )

        found = False

        for address, (device, adv) in devices.items():
            name = adv.local_name or device.name or ""

            if name == TARGET_NAME:
                found = True
                print(f"Device: {name}")
                print(f"Address: {address}")
                print(f"Signal strength: {adv.rssi} dBm")
                print(f"Manufacturer data: {adv.manufacturer_data}")
                print("-" * 35)

        if not found:
            print(f"{TARGET_NAME} not detected. Retrying...")

asyncio.run(main())
