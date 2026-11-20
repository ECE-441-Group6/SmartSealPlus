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


async def scan_real_ble():
    """Collect authenticated XIAO manufacturer advertisements for one window."""
    xiao_device = None
    packets_by_seal = {}

    def detection_callback(device, advertisement):
        nonlocal xiao_device
        # Use the name only to report discovery; packet acceptance is based on
        # the encrypted, authenticated manufacturer payload.
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
        # Bleak delivers each received advertisement to the callback until this
        # window closes; scan all seals before handing packets to the gateway.
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        await scanner.stop()

    if packets_by_seal:
        packets = list(packets_by_seal.values())
        print(f"XIAO BLE packets received from {len(packets)} seal(s).")
        for packet in packets:
            print(f"XIAO BLE advertisement: {packet}")
        # Keep the old single-packet return shape when only one seal was seen.
        return packets[0] if len(packets) == 1 else packets

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
        return None

    print(
        "XIAO was found, but no SmartSeal manufacturer advertisement "
        "was received. Ensure the updated firmware is uploaded."
    )
    return None


def scan_ble():
    """Return one XIAO packet from BLE."""
    if SIMULATION_MODE:
        packet = simulated_packet()
        print(f"SIMULATED XIAO packet: {packet}")
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
        print(f"XIAO BLE SCANNING ERROR: {type(error).__name__}: {error}")
        return None


if __name__ == "__main__":
    print("Scanner result:", scan_ble())
