#The purpose of this file is to scan for the SmartSeal+ BLE device and display its information.
#Run the following command to execute this script:
#cd ~/SmartSealPlus/TestFiles
#python3 scan_smartseal.py

import asyncio
import re
from bleak import BleakScanner

TARGET_NAME = "Xiao_Recorder"
MANUFACTURER_ID = 0x5353
PACKET_PATTERN = re.compile(
    r"S:\d+,T:[-+]?\d+(?:\.\d+)?,A:[01],V:[01]"
)

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
            manufacturer_data = adv.manufacturer_data
            payload = manufacturer_data.get(MANUFACTURER_ID)

            if payload is None:
                continue

            message = payload.decode("utf-8", errors="replace").strip()
            if not PACKET_PATTERN.fullmatch(message):
                continue

            found = True
            print(f"Device: {name or TARGET_NAME}")
            print(f"Address: {address}")
            print(f"Signal strength: {adv.rssi} dBm")
            print(f"SmartSeal packet: {message}")
            print(f"Manufacturer data: {manufacturer_data}")
            print("-" * 35)

        if not found:
            print(f"{TARGET_NAME} not detected. Retrying...")

asyncio.run(main())
