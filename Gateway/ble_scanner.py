"""Receive SmartSeal sensor packets over BLE advertisements."""

import os
import random

import asyncio
from bleak import BleakScanner
from bleak.exc import BleakError
from cryptography.hazmat.primitives.ciphers.aead import AESCCM

try:
    from .key_registry import KeyRegistryError, load_key_registry
except ImportError:
    from key_registry import KeyRegistryError, load_key_registry

MANUFACTURER_ID = 0x5353
ESP_DEVICE_NAMES = {"SmartSeal-01"} 
XIAO_DEVICE_NAME = "Xiao_Recorder"
XIAO_DEVICE_NAMES = {XIAO_DEVICE_NAME, "SmartSeal-XIAO"}
ENCRYPTED_PACKET_VERSION = 2
ENCRYPTED_PACKET_LENGTH = 24
SCAN_TIMEOUT = 5.0
SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"


def _decrypt_encrypted_packet(payload, keys_by_seal):
    nonce = payload[1:8]
    ciphertext_and_tag = payload[8:]
    for seal_id, key in keys_by_seal.items():
        try:
            plaintext = AESCCM(key, tag_length=6).decrypt(
                nonce,
                ciphertext_and_tag,
                payload[:1],
            )
        except Exception:
            continue

        if len(plaintext) != 10 or plaintext[0] != seal_id:
            continue
        return {
            "seal_id": seal_id,
            "event_sequence": int.from_bytes(plaintext[1:5], "little"),
            "temperature": int.from_bytes(
                plaintext[5:7], "little", signed=True
            ) / 10.0,
            "tamper": bool(plaintext[7]),
            "vibration": int.from_bytes(
                plaintext[8:10], "little"
            ) / 100.0,
        }
    return None


def parse_advertisement(payload, keys_by_seal=None):
    """Convert an ESP32 or XIAO manufacturer payload into a gateway packet."""
    if payload is None:
        return None

    if isinstance(payload, (bytes, bytearray)):
        # Bleak normally removes the company ID. Accept it too for backends
        # that expose the raw manufacturer field.
        if payload.startswith(b"\x53\x53"):
            payload = payload[2:]
        if (
            len(payload) == ENCRYPTED_PACKET_LENGTH
            and payload[0] == ENCRYPTED_PACKET_VERSION
        ):
            try:
                keys_by_seal = (
                    load_key_registry()
                    if keys_by_seal is None
                    else keys_by_seal
                )
            except KeyRegistryError as error:
                print(f"BLE key registry error: {error}")
                return None
            return _decrypt_encrypted_packet(payload, keys_by_seal)
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
        "Check that the XIAO is advertising the 0x5353 manufacturer data, "
        "that a matching key is configured, and press D6 to start live "
        "sensor updates."
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
