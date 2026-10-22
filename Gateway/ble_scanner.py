"""Receive SmartSeal sensor packets over BLE."""

import asyncio
import os
import random
import re

from bleak import BleakScanner

MANUFACTURER_ID = 0x5353
DEVICE_NAME = "SmartSeal-01"
SCAN_TIMEOUT = 5.0
SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"


def parse_advertisement(payload):
    """Convert the ESP32 manufacturer payload into a gateway packet."""
    if payload is None:
        return None

    if isinstance(payload, bytes):
        # Bleak normally removes the company ID. Accept it too for backends
        # that expose the raw manufacturer field.
        if payload.startswith(b"\x53\x53"):
            payload = payload[2:]
        payload = payload.decode("ascii", errors="ignore")

    match = re.fullmatch(
        r"S:(\d+),T:([-+]?\d+(?:\.\d+)?),A:([01]),V:([01])",
        payload.strip(),
    )
    if not match:
        return None

    seal_id, temperature, tamper, vibration = match.groups()
    return {
        "seal_id": int(seal_id),
        "temperature": float(temperature),
        "tamper": tamper == "1",
        "vibration": vibration == "1",
    }


def simulated_packet():
    """Generate a packet when a BLE adapter or ESP32 is not available."""
    return {
        "seal_id": 1,
        "temperature": round(random.uniform(1.0, 10.0), 1),
        "tamper": random.choice([True, False]),
        "vibration": random.choice([True, False]),
    }


async def scan_real_ble():
    """Scan for the latest valid SmartSeal manufacturer advertisement."""
    packets = []

    def detection_callback(device, advertisement):
        payload = advertisement.manufacturer_data.get(MANUFACTURER_ID)
        if payload is None:
            return

        # The device name may be placed in a scan response or omitted when the
        # advertisement is full. The SmartSeal company ID and payload are the
        # reliable protocol identifiers, so do not require the name here.
        packet = parse_advertisement(payload)
        if packet is not None:
            packets.append(packet)

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    try:
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        await scanner.stop()

    if not packets:
        print(f"No valid {DEVICE_NAME} BLE advertisement received.")
        return None

    packet = packets[-1]
    print(f"BLE packet received: {packet}")
    return packet


def scan_ble():
    """Return one ESP32 packet, using simulation only when explicitly enabled."""
    if SIMULATION_MODE:
        packet = simulated_packet()
        print(f"SIMULATED packet: {packet}")
        return packet

    try:
        return asyncio.run(scan_real_ble())
    except Exception as error:
        print(f"BLE scanning error: {error}")
        return None


if __name__ == "__main__":
    print("Scanner result:", scan_ble())
