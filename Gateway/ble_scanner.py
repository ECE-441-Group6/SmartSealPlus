# Reads BLE advertisements from nearby ESP32-C3 SmartSeals.
# The simulator uses this same packet shape until real BLE hardware is available.
import random


def scan_ble():
    #Return one simulated ESP32 sensor advertisement.

    #Replace this function with a real BLE scan that decodes advertisements
    #from the ESP32 when hardware communication is implemented.
    
    # Random values let the complete gateway and dashboard flow be exercised
    # without an ESP32 or a Bluetooth adapter.
    return {
        "seal_id": 1,
        "temperature": round(random.uniform(1.0, 10.0), 1),
        "tamper": random.choice([True, False]),
        "vibration": random.choice([True, False]),
    }

"""
SmartSeal+ BLE scanner.

Supports:
1. Real BLE advertisements from ESP32 SmartSeals.
2. A simulator fallback for development and testing.

Expected manufacturer data:
    Manufacturer ID: 0x5353
    Payload: S:1,T:4.5,A:0,V:0
"""
"""
import asyncio
import os
import random
import re

from bleak import BleakScanner

MANUFACTURER_ID = 0x5353
SCAN_TIMEOUT = 5.0

# Set SMARTSEAL_SIMULATION=1 to use simulated data.
SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"

def parse_advertisement(payload):
    #Convert a SmartSeal text payload into the packet dictionary
    #expected by packet_parser.py.

    if isinstance(payload, bytes):
        payload = payload.decode("ascii", errors="ignore")

    payload = payload.strip()

    match = re.fullmatch(
        r"S:(\d+),T:([-+]?\d+(?:\.\d+)?),A:([01]),V:([01])",
        payload,
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
    #Generate a simulated reading for software testing.

    return {
        "seal_id": 1,
        "temperature": round(random.uniform(1.0, 10.0), 1),
        "tamper": random.choice([True, False]),
        "vibration": random.choice([True, False]),
    }


async def scan_real_ble():
    #Scan for ESP32 advertisements and return the first valid SmartSeal sensor packet.
    #Returns None if no valid packet is received.

    def detection_callback(device, advertisement):
        manufacturer_data = advertisement.manufacturer_data

        if MANUFACTURER_ID not in manufacturer_data:
            return

        packet = parse_advertisement(
            manufacturer_data[MANUFACTURER_ID]
        )

        if packet is not None:
            packets.append(packet)

    packets = []

    scanner = BleakScanner(
        detection_callback=detection_callback
    )

    await scanner.start()

    try:
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        await scanner.stop()

    if packets:
        packet = packets[-1]
        print(f"BLE packet received: {packet}")
        return packet

    print("No valid SmartSeal BLE advertisement received.")
    return None

def scan_ble():
    
    #Gateway-compatible entry point.

    #Returns a packet dictionary or None.
    

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
    packet = scan_ble()
    print("Scanner result:", packet)
"""