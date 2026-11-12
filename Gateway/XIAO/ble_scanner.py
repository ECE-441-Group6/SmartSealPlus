"""Receive SmartSeal sensor packets from XIAO BLE advertisements."""

import asyncio
import os

from bleak import BleakScanner
from bleak.exc import BleakError

from Gateway.ble_scanner import (
    MANUFACTURER_ID,
    SCAN_TIMEOUT,
    XIAO_DEVICE_NAME,
    parse_advertisement,
    simulated_packet,
)

SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"


async def scan_real_ble_packets():
    """Return the newest packet observed from each seal in range."""
    xiao_device = None
    packets_by_seal = {}

    def detection_callback(device, advertisement):
        nonlocal xiao_device
        device_name = advertisement.local_name or device.name or ""
        packet = None
        for manufacturer_id, payload in advertisement.manufacturer_data.items():
            if manufacturer_id == MANUFACTURER_ID:
                packet = parse_advertisement(payload)
            if packet is None and isinstance(payload, (bytes, bytearray)):
                packet = parse_advertisement(payload)
            if packet is not None:
                break
        if device_name == XIAO_DEVICE_NAME:
            xiao_device = device
        if packet is not None:
            packets_by_seal[packet["seal_id"]] = packet
            xiao_device = device

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    try:
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        await scanner.stop()

    if packets_by_seal:
        packets = list(packets_by_seal.values())
        print(
            "XIAO BLE packets received from seals:",
            ", ".join(str(packet["seal_id"]) for packet in packets),
        )
        return packets

    if xiao_device is None:
        try:
            xiao_device = await BleakScanner.find_device_by_name(
                XIAO_DEVICE_NAME,
                timeout=SCAN_TIMEOUT,
            )
        except (BleakError, OSError, asyncio.TimeoutError) as error:
            print(f"XIAO BLE discovery error: {error}")

    if xiao_device is None:
        print("No valid BLE packet received from SmartSeal-XIAO.")
        return []

    print(
        "XIAO was found, but no SmartSeal manufacturer advertisement "
        "was received. Ensure the updated firmware is uploaded."
    )
    return []


def scan_ble():
    """Return one XIAO packet for callers that expect the old interface."""
    if SIMULATION_MODE:
        packet = simulated_packet()
        print(f"SIMULATED XIAO packet: {packet}")
        return packet

    try:
        packets = asyncio.run(scan_real_ble_packets())
        return packets[-1] if packets else None
    except RuntimeError as error:
        if "asyncio.run() cannot be called" in str(error):
            print(f"ASYNCIO EVENT LOOP ERROR: {error}")
        else:
            print(f"RUNTIME ERROR DURING BLE SCAN: {error}")
        return None
    except Exception as error:
        print(f"XIAO BLE SCANNING ERROR: {type(error).__name__}: {error}")
        return None


def scan_ble_packets():
    """Return the newest packet observed from each seal in one scan."""
    if SIMULATION_MODE:
        packet = simulated_packet()
        print(f"SIMULATED XIAO packet: {packet}")
        return [packet]

    try:
        return asyncio.run(scan_real_ble_packets())
    except RuntimeError as error:
        if "asyncio.run() cannot be called" in str(error):
            print(f"ASYNCIO EVENT LOOP ERROR: {error}")
        else:
            print(f"RUNTIME ERROR DURING BLE SCAN: {error}")
        return []
    except Exception as error:
        print(f"XIAO BLE SCANNING ERROR: {type(error).__name__}: {error}")
        return []


if __name__ == "__main__":
    print("Scanner result:", scan_ble_packets())
