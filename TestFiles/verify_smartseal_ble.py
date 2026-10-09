#The purpose of this file is to verify the BLE advertising of the SmartSeal+ device by scanning for it and displaying its information.
#Run the following command to execute this script:
#cd ~/SmartSealPlus/TestFiles
#~/ble-venv/bin/python verify_smartseal_ble.py

import asyncio
from bleak import BleakScanner

TARGET_NAME = "SmartSeal-01"

async def main():
    print(f"Scanning for {TARGET_NAME}...")
    print("Press Ctrl+C to stop.\n")

    while True:
        devices = await BleakScanner.discover(
            timeout=5,
            return_adv=True
        )

        for address, (device, adv) in devices.items():
            name = adv.local_name or device.name or ""

            if name != TARGET_NAME:
                continue

            print("=" * 45)
            print(f"Device name: {name}")
            print(f"Address: {address}")
            print(f"RSSI: {adv.rssi} dBm")

            print("\nManufacturer data:")
            if adv.manufacturer_data:
                for company_id, data in adv.manufacturer_data.items():
                    print(f"  ID: 0x{company_id:04X}")
                    print(f"  Hex: {data.hex()}")
                    print(f"  Text: {data.decode('utf-8', errors='replace')}")
            else:
                print("  None received")

            print("\nService data:")
            if adv.service_data:
                for uuid, data in adv.service_data.items():
                    print(f"  UUID: {uuid}")
                    print(f"  Data: {data.hex()}")
            else:
                print("  None received")

            print("\nService UUIDs:", adv.service_uuids)
            print()

asyncio.run(main())
