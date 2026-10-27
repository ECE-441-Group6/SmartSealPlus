"""Receive SmartSeal sensor packets from the XIAO GATT characteristic."""

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
    """Find the XIAO and receive its sensor packet over BLE."""
    xiao_device = None
    advertised_packet = None
    packet_received = asyncio.Event()

    def detection_callback(device, advertisement):
        nonlocal advertised_packet, xiao_device
        device_name = advertisement.local_name or device.name or ""
        payload = advertisement.manufacturer_data.get(MANUFACTURER_ID)
        packet = parse_advertisement(payload)
        if device_name == XIAO_DEVICE_NAME:
            xiao_device = device
        if packet is not None:
            advertised_packet = packet
            xiao_device = device
            packet_received.set()

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    try:
        try:
            await asyncio.wait_for(packet_received.wait(), SCAN_TIMEOUT)
        except asyncio.TimeoutError:
            pass
    finally:
        await scanner.stop()

    if advertised_packet is not None and xiao_device is not None:
        print(f"XIAO BLE advertisement received: {advertised_packet}")
        return advertised_packet

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

    print("XIAO was found, but no sensor advertisement was received.")
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
