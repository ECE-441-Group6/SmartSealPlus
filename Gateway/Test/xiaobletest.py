import asyncio
from bleak import BleakScanner

async def main():
    def on_advertisement(device, adv):
        for company_id, payload in adv.manufacturer_data.items():
            if company_id == 0x5353:
                print(
                    f"{adv.local_name or device.name or device.address}: "
                    f"company=0x{company_id:04X} "
                    f"payload={payload.hex(' ')}"
                )

    scanner = BleakScanner(detection_callback=on_advertisement)
    await scanner.start()
    try:
        await asyncio.sleep(30)
    finally:
        await scanner.stop()

asyncio.run(main())