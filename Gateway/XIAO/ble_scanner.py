"""Receive SmartSeal sensor packets from XIAO BLE advertisements."""

import asyncio
import os

from bleak import BleakScanner

from Gateway.ble_scanner import (
    MANUFACTURER_ID,
    SCAN_TIMEOUT,
    XIAO_DEVICE_NAME,
    XIAO_DEVICE_NAMES,
    parse_advertisement,
    simulated_packet,
)

SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"


async def scan_real_ble():
    """Find the XIAO and receive its sensor packet over BLE."""
    xiao_device = None
    advertised_packet = None
    advertisements_seen = 0
    manufacturer_packets_seen = 0
    encrypted_candidates_seen = 0
    authentication_failures = 0
    packet_received = asyncio.Event()

    def detection_callback(device, advertisement):
        nonlocal advertised_packet, xiao_device, advertisements_seen
        nonlocal manufacturer_packets_seen, encrypted_candidates_seen
        nonlocal authentication_failures
        advertisements_seen += 1
        device_name = advertisement.local_name or device.name or ""
        packet = None
        for manufacturer_id, payload in advertisement.manufacturer_data.items():
            if manufacturer_id == MANUFACTURER_ID:
                manufacturer_packets_seen += 1
                if (
                    isinstance(payload, (bytes, bytearray))
                    and len(payload) == 24
                    and payload[0] == 2
                ):
                    encrypted_candidates_seen += 1
                packet = parse_advertisement(payload)
                if packet is None and (
                    isinstance(payload, (bytes, bytearray))
                    and len(payload) == 24
                    and payload[0] == 2
                ):
                    authentication_failures += 1
            if packet is not None:
                break
        if device_name in XIAO_DEVICE_NAMES:
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

    if advertised_packet is not None:
        print(f"XIAO BLE advertisement received: {advertised_packet}")
        return advertised_packet

    if xiao_device is None:
        if advertisements_seen == 0:
            print(
                "No BLE advertisements were received. Check that the adapter "
                "is enabled and accessible to this user."
            )
        elif manufacturer_packets_seen == 0:
            print(
                f"Received {advertisements_seen} BLE advertisements, but none "
                f"used SmartSeal manufacturer ID 0x{MANUFACTURER_ID:04X}. "
                "Check the firmware build and upload."
            )
        elif encrypted_candidates_seen == 0:
            print(
                f"Received {manufacturer_packets_seen} SmartSeal manufacturer "
                "payload(s), but none had the expected 24-byte version-2 "
                "encrypted format. Press D6 to start recording and check the "
                "uploaded firmware."
            )
        elif authentication_failures:
            print(
                f"Received {authentication_failures} version-2 packet(s), "
                "but AES-CCM authentication failed. The firmware secret and "
                "gateway key registry may not match."
            )
        else:
            print(
                "Received SmartSeal manufacturer data, but no valid packet "
                "was accepted. Check packet version and length."
            )
        return None

    print(
        f"Found {XIAO_DEVICE_NAME}, but no valid SmartSeal packet arrived in "
        f"{SCAN_TIMEOUT:g} seconds. Press D6 to start recording. "
        f"Manufacturer payloads seen: {manufacturer_packets_seen}; "
        f"version-2 candidates: {encrypted_candidates_seen}; "
        f"authentication failures: {authentication_failures}."
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
