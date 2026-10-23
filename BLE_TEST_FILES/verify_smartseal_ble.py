# The purpose of this file is to verify BLE advertising from the SmartSeal+
# device and the XIAO nRF52840.
#Run the following command to execute this script:
#cd ~/SmartSealPlus/TestFiles
#python3 verify_smartseal_ble.py

import asyncio
import re
from bleak import BleakScanner

TARGET_NAMES = {"SmartSeal-01", "Xiao_Recorder"}
MANUFACTURER_ID = 0x5353
PACKET_PATTERN = re.compile(
    r"^S:(\d+),T:([-+]?\d+(?:\.\d+)?),A:([01]),V:([-+]?\d+(?:\.\d+)?)$"
)


def decode_packet(data):
    """Decode manufacturer data with or without an embedded company ID."""
    if data.startswith(b"\x53\x53"):
        data = data[2:]

    message = data.decode("ascii", errors="replace").strip()
    return message if PACKET_PATTERN.fullmatch(message) else None


async def main():
    names = ", ".join(sorted(TARGET_NAMES))
    print(f"Scanning for BLE packets from: {names}")
    print(f"Manufacturer ID: 0x{MANUFACTURER_ID:04X}")
    print("Press Ctrl+C to stop.\n")

    last_packets = {}

    while True:
        devices = await BleakScanner.discover(
            timeout=3,
            return_adv=True
        )

        for address, (device, adv) in devices.items():
            name = adv.local_name or device.name or ""

            for company_id, data in adv.manufacturer_data.items():
                if company_id != MANUFACTURER_ID:
                    continue

                message = decode_packet(data)
                if message is None:
                    continue

                packet_key = (address, message)
                if packet_key == last_packets.get(address):
                    continue

                last_packets[address] = packet_key
                seal_id, temperature, tamper, vibration = (
                    PACKET_PATTERN.fullmatch(message).groups()
                )
                print("BLE packet received")
                print(f"  Device: {name or 'unnamed'}")
                print(f"  Address: {address}")
                print(f"  RSSI: {adv.rssi} dBm")
                print(f"  Packet: {message}")
                print(
                    f"  Parsed: seal_id={seal_id}, temperature={temperature}, "
                    f"tamper={tamper}, vibration={vibration}"
                )
                print(f"  Raw payload: {data.hex(' ')}")
                print("-" * 45)

if __name__ == "__main__":
    asyncio.run(main())
