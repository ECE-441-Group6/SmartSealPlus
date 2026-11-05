"""Receive SmartSeal sensor packets over BLE advertisements."""

import os
import random

import asyncio
from bleak import BleakScanner
from bleak.exc import BleakError

MANUFACTURER_ID = 0x5353
ESP_DEVICE_NAMES = {"SmartSeal-01"} 
XIAO_DEVICE_NAME = "Xiao_Recorder"
XIAO_DEVICE_NAMES = {XIAO_DEVICE_NAME, "SmartSeal-XIAO"}
ADVERTISEMENT_PACKET_VERSION = 1
ADVERTISEMENT_PACKET_LENGTH = 11
SCAN_TIMEOUT = 15.0
SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"


def parse_advertisement(payload):
    """Decode the version-1 plaintext sensor manufacturer payload."""
    if not isinstance(payload, (bytes, bytearray)):
        return None

    # Bleak normally strips the company identifier from manufacturer data.
    # Some backends return it with the payload instead.
    if payload.startswith(b"\x53\x53"):
        payload = payload[2:]
    if (
        len(payload) != ADVERTISEMENT_PACKET_LENGTH
        or payload[0] != ADVERTISEMENT_PACKET_VERSION
    ):
        return None

    seal_id = payload[1]
    sequence = int.from_bytes(payload[2:6], "little")
    temperature_tenths = int.from_bytes(payload[6:8], "little", signed=True)
    tamper = payload[8]
    if seal_id < 1 or tamper not in (0, 1):
        return None

    temperature = (
        None if temperature_tenths == 0x7FFF
        else temperature_tenths / 10.0
    )
    return {
        "seal_id": seal_id,
        "event_sequence": sequence,
        "temperature": temperature,
        "tamper": bool(tamper),
        "vibration": int.from_bytes(payload[9:11], "little") / 100.0,
    }


def simulated_packet():
    """Generate a packet when a BLE adapter or ESP32 is not available."""
    simulated_packet.sequence = (getattr(simulated_packet, "sequence", 0) + 1) & 0xFFFFFFFF
    return {
        "seal_id": 1,
        "event_sequence": simulated_packet.sequence,
        "temperature": round(random.uniform(1.0, 10.0), 1),
        "tamper": random.choice([True, False]),
        "vibration": round(random.uniform(0.0, 3.05), 2),
    }


async def scan_real_ble():
    """Scan for SmartSeal packets in BLE manufacturer advertisements."""
    packets = []
    xiao_device = None

    def detection_callback(device, advertisement):
        nonlocal xiao_device
        device_name = advertisement.local_name or device.name or ""
        service_uuids = {
            uuid.lower() for uuid in (advertisement.service_uuids or [])
        }
        is_xiao = (
            device_name in XIAO_DEVICE_NAMES
            or "0000180f-0000-1000-8000-00805f9b34fb" in service_uuids
            or "180f" in service_uuids
        )
        if is_xiao:
            xiao_device = device

        payloads = (
            payload
            for company_id, payload in advertisement.manufacturer_data.items()
            if company_id == MANUFACTURER_ID
        )
        # The device name may be placed in a scan response or omitted when the
        # advertisement is full. The company ID and payload are the reliable
        # protocol identifiers, so do not require the name here.
        packet = None
        for payload in payloads:
            packet = parse_advertisement(payload)
            if packet is not None:
                break
        if packet is not None:
            packets.append(packet)
        elif advertisement.manufacturer_data:
            print(
                "Ignoring invalid manufacturer payload from "
                f"{device.name or 'unnamed'}: "
                f"{advertisement.manufacturer_data!r}"
            )

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    try:
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        await scanner.stop()

    #tries to scan for xiao again
    if xiao_device is None and not packets:
        try:
            xiao_device = await BleakScanner.find_device_by_name(
                XIAO_DEVICE_NAME,
                timeout=SCAN_TIMEOUT,
            )
        except (BleakError, OSError, asyncio.TimeoutError) as error:
            print(f"XIAO BLE discovery error: {error}")

    #but packets list will always be empty since code below line 94 wont run? also this will only return the most recent packet, not all of the packets received
    if packets:
        packet = packets[-1]
        print(f"BLE packet received: {packet}")
        return packet

    print(
        "No valid BLE packet received from "
        f"{', '.join(sorted(ESP_DEVICE_NAMES | XIAO_DEVICE_NAMES))}."
    )
    print(
        "Check that the XIAO is advertising the 0x5353 manufacturer data "
        "and press D6 to start live sensor updates."
    )
    return None


def scan_ble():
    """Return one ESP32 packet, using simulation only when explicitly enabled."""

    if SIMULATION_MODE:
        packet = simulated_packet()
        print(f"SIMULATED packet: {packet}")
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
        print(f"BLE SCANNING ERROR: {type(error).__name__}: {error}")
        return None


if __name__ == "__main__":
    print("Scanner result:", scan_ble())
