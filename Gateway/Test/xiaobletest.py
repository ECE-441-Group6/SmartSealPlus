#Run with ble_test.cpp in XIAOnRF8540 folder
import asyncio
from bleak import BleakScanner, BleakClient

DEVICE_NAME = "SmartSeal-XIAO"

async def main():
    print(f"Scanning for {DEVICE_NAME}...")
    device = await BleakScanner.find_device_by_name(
        DEVICE_NAME, timeout=15
    )

    if device is None:
        print("Device not found.")
        return

    print(f"Found device: {device.name}")
    print(f"Address: {device.address}")
    print("Connecting...")

    async with BleakClient(device) as client:
        print(f"Connected: {client.is_connected}")
        print("\nDiscovering services...")

        for service in client.services:
            print(f"\nService UUID: {service.uuid}")
            print(f"  Description: {service.description}")

            for characteristic in service.characteristics:
                print(f"  Characteristic UUID: {characteristic.uuid}")
                print(f"    Properties: {characteristic.properties}")

                try:
                    value = await client.read_gatt_char(
                        characteristic.uuid
                    )
                    print(f"    Read value: {value!r}")
                except Exception as e:
                    print(f"    Read unavailable: {e}")

        print("\nKeeping connection open for 10 seconds...")
        await asyncio.sleep(10)

asyncio.run(main())
