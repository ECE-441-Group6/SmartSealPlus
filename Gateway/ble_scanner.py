"""Receive SmartSeal sensor packets over BLE advertisements."""

import os
import random
import asyncio

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
from bleak import BleakScanner
from bleak.exc import BleakError

try:
    from .key_registry import load_key_registry
except ImportError:
    from key_registry import load_key_registry


MANUFACTURER_ID = 0x5353
XIAO_DEVICE_NAME = "SmartSeal-XIAO"
SCAN_TIMEOUT = 5.0
SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"
PACKET_VERSION = 2
NONCE_LENGTH = 7
PLAINTEXT_LENGTH = 10
TAG_LENGTH = 8
PACKET_LENGTH = 1 + NONCE_LENGTH + PLAINTEXT_LENGTH + TAG_LENGTH
PACKET_VERSION_AAD = bytes([PACKET_VERSION])


def parse_advertisement(payload, key_registry=None):
    """Authenticate and decode a version-2 AES-CCM manufacturer payload."""
    if not isinstance(payload, (bytes, bytearray)):
        return None

    payload = bytes(payload)
    if payload.startswith(b"\x53\x53"):
        payload = payload[2:]
    if len(payload) != PACKET_LENGTH or payload[0] != PACKET_VERSION:
        return None

    keys = load_key_registry() if key_registry is None else key_registry
    nonce = payload[1:1 + NONCE_LENGTH]
    ciphertext_and_tag = payload[1 + NONCE_LENGTH:]
    ciphertext = ciphertext_and_tag[:-TAG_LENGTH]
    tag = ciphertext_and_tag[-TAG_LENGTH:]

    for registered_seal_id, key in keys.items():
        try:
            plaintext = AESCCM(key, tag_length=TAG_LENGTH).decrypt(
                nonce,
                ciphertext + tag,
                PACKET_VERSION_AAD,
            )
        except InvalidTag:
            continue

        seal_id = plaintext[0]
        if seal_id != registered_seal_id or plaintext[7] not in (0, 1):
            return None

        return {
            "seal_id": seal_id,
            "event_sequence": int.from_bytes(plaintext[1:5], "little"),
            "temperature": int.from_bytes(
                plaintext[5:7], "little", signed=True
            ) / 10.0,
            "tamper": bool(plaintext[7]),
            "vibration": int.from_bytes(plaintext[8:10], "little") / 100.0,
        }

    return None


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
    key_registry = load_key_registry()
    packets = []
    xiao_device = None

    def detection_callback(device, advertisement):
        nonlocal xiao_device
        device_name = advertisement.local_name or device.name or ""
        if device_name == XIAO_DEVICE_NAME:
            xiao_device = device

        payload = advertisement.manufacturer_data.get(MANUFACTURER_ID)
        packet = parse_advertisement(payload, key_registry) if payload else None
        if packet is not None:
            packets.append(packet)
        elif payload:
            print(
                "Ignoring invalid or unauthenticated BLE packet from "
                f"{device.name or 'unnamed'}."
            )

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    try:
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        await scanner.stop()

    if xiao_device is None and not packets:
        try:
            xiao_device = await BleakScanner.find_device_by_name(
                XIAO_DEVICE_NAME,
                timeout=SCAN_TIMEOUT,
            )
        except (BleakError, OSError, asyncio.TimeoutError) as error:
            print(f"XIAO BLE discovery error: {error}")

    if packets:
        packet = packets[-1]
        print(f"BLE packet received: {packet}")
        return packet

    print(
        "No valid BLE packet received from "
        f"{XIAO_DEVICE_NAME}."
    )
    print(
        "Check that the XIAO is advertising and has the provisioned "
        "encrypted firmware uploaded."
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

    except (BleakError, OSError, asyncio.TimeoutError) as error:
        print(f"BLE SCANNING ERROR: {type(error).__name__}: {error}")
        return None


if __name__ == "__main__":
    print("Scanner result:", scan_ble())
