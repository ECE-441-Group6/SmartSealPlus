"""Receive SmartSeal sensor packets from ESP32 BLE advertisements."""

import asyncio
import os

from bleak import BleakScanner
from bleak import BleakClient
from bleak.exc import BleakError

from Gateway.ble_scanner import (
    MANUFACTURER_ID,
    SCAN_TIMEOUT,
    parse_advertisement,
    simulated_packet,
    write_ack,
)

SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"
ACK_CHARACTERISTIC_UUID = "12345678-1234-1234-1234-1234567890ad"


async def scan_real_ble():
    """Scan for the ESP32 manufacturer payload and return its latest packet."""
    packets = []
    packet_devices = {}

    def detection_callback(device, advertisement):
        payload = advertisement.manufacturer_data.get(MANUFACTURER_ID)
        if payload is None:
            return

        packet = parse_advertisement(payload)
        if packet is not None:
            packets.append(packet)
            packet_devices[id(packet)] = device
        else:
            print(
                "Ignoring invalid manufacturer payload from "
                f"{device.name or 'unnamed'}: {payload!r}"
            )

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    try:
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        await scanner.stop()

    if not packets:
        print("No valid BLE packet received from SmartSeal-01.")
        return None

    packet = packets[-1]
    device = packet_devices[id(packet)]
    print(f"ESP32 BLE packet received: {packet}")
    packet["_acknowledge"] = lambda: asyncio.run(
        write_ack(device, ACK_CHARACTERISTIC_UUID, packet)
    )
    return packet


def scan_ble():
    """Return one ESP32 packet from BLE."""
    if SIMULATION_MODE:
        packet = simulated_packet()
        print(f"SIMULATED ESP32 packet: {packet}")
        return packet

    try:
        return asyncio.run(scan_real_ble())
    except RuntimeError as error:
        if "asyncio.run() cannot be called" in str(error):
            print(f"ASYNCIO EVENT LOOP ERROR: {error}")
        else:
            print(f"RUNTIME ERROR DURING BLE SCAN: {error}")
        return None
    except Exception as error:
        print(f"ESP32 BLE SCANNING ERROR: {type(error).__name__}: {error}")
        return None


if __name__ == "__main__":
    print("Scanner result:", scan_ble())
