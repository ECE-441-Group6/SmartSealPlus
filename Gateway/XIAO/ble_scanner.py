"""Receive SmartSeal sensor packets from the XIAO GATT characteristic."""

import asyncio
import os

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from Gateway.ble_scanner import (
    SCAN_TIMEOUT,
    XIAO_CHARACTERISTIC_UUID,
    XIAO_DEVICE_NAME,
    parse_xiao_message,
    simulated_packet,
)

XIAO_SERVICE_UUIDS = {
    "0000180f-0000-1000-8000-00805f9b34fb",
    "180f",
}
SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"


async def scan_real_ble():
    """Find the XIAO and read its sensor packet over GATT."""
    xiao_device = None

    def detection_callback(device, advertisement):
        nonlocal xiao_device
        device_name = advertisement.local_name or device.name or ""
        service_uuids = {
            uuid.lower() for uuid in (advertisement.service_uuids or [])
        }
        if (
            device_name == XIAO_DEVICE_NAME
            or XIAO_SERVICE_UUIDS.intersection(service_uuids)
        ):
            xiao_device = device

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    try:
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        await scanner.stop()

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

    try:
        async with BleakClient(xiao_device) as client:
            payload = await client.read_gatt_char(XIAO_CHARACTERISTIC_UUID)
        packet = parse_xiao_message(payload)
        if packet is None:
            print("XIAO BLE characteristic did not contain a sensor packet.")
            return None
        print(f"XIAO BLE packet received: {packet}")
        return packet
    except (BleakError, OSError, asyncio.TimeoutError) as error:
        print(f"XIAO BLE read error: {error}")
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
