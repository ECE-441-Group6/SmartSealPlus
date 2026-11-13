
"""Receive and decrypt SmartSeal BLE advertisements."""

import os
import random
import asyncio
import json
from pathlib import Path

from bleak import BleakScanner
from bleak.exc import BleakError
from cryptography.hazmat.primitives.ciphers.aead import AESCCM


# --------------------------------------------------
# BLE CONFIGURATION
# --------------------------------------------------

MANUFACTURER_ID = 0x5353
XIAO_DEVICE_NAME = "SmartSeal-XIAO"
ESP_DEVICE_NAMES = {"SmartSeal-01"}

SCAN_TIMEOUT = 5.0

SIMULATION_MODE = (
    os.getenv("SMARTSEAL_SIMULATION", "0") == "1"
)


# --------------------------------------------------
# AES-128-CCM CONFIGURATION
# --------------------------------------------------

def _load_hex_secret(name, length):
    """Load a fixed-length hexadecimal secret from the local key file."""
    key_path = Path(__file__).with_name("keys.json")
    try:
        with key_path.open(encoding="utf-8") as key_file:
            value = json.load(key_file)[name]
    except (OSError, KeyError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not load {name} from {key_path}."
        ) from error

    try:
        secret = bytes.fromhex(value)
    except ValueError as error:
        raise RuntimeError(
            f"{name} must contain hexadecimal bytes."
        ) from error

    if len(secret) != length:
        raise RuntimeError(
            f"{name} must be exactly {length} bytes "
            f"({length * 2} hexadecimal characters)."
        )

    return secret


AES_KEY = _load_hex_secret("SMARTSEAL_AES_KEY", 16)
NONCE_PREFIX = _load_hex_secret("SMARTSEAL_NONCE_PREFIX", 9)

AES_TAG_LENGTH = 8

MAGIC = 0xA5
PROTOCOL_VERSION = 3

EXPECTED_PACKET_LENGTH = 21

aes = AESCCM(AES_KEY, tag_length=AES_TAG_LENGTH)


# --------------------------------------------------
# DECRYPTION
# --------------------------------------------------

def parse_advertisement(payload):
    """
    Decrypt and authenticate a SmartSeal BLE advertisement.

    Expected packet:
        Byte 0:       Magic (0xA5)
        Byte 1:       Protocol version (3)
        Byte 2:       Seal ID
        Bytes 3-6:    Sequence number (little-endian)
        Bytes 7-12:   Encrypted sensor data
        Bytes 13-20:  AES-CCM authentication tag
    """

    if payload is None:
        return None

    if not isinstance(payload, (bytes, bytearray)):
        return None

    payload = bytes(payload)

    # Bleak normally removes the manufacturer/company ID.
    # Accept it if a backend includes it.
    if payload.startswith(b"\x53\x53"):
        payload = payload[2:]

    # Validate packet length.
    if len(payload) != EXPECTED_PACKET_LENGTH:
        return None

    # Validate header.
    if payload[0] != MAGIC:
        return None

    if payload[1] != PROTOCOL_VERSION:
        return None

    seal_id = payload[2]

    if seal_id < 1:
        return None

    # Extract sequence number.
    sequence_bytes = payload[3:7]

    sequence = int.from_bytes(
        sequence_bytes,
        byteorder="little"
    )

    # Nonce must match the XIAO implementation exactly.
    # Use the transmitted sequence bytes directly.
    nonce = NONCE_PREFIX + sequence_bytes

    # Authenticate header and sequence.
    aad = payload[0:7]

    # Ciphertext and authentication tag.
    ciphertext_and_tag = payload[7:21]

    try:
        plaintext = aes.decrypt(
            nonce,
            ciphertext_and_tag,
            aad
        )

    except Exception:
        print(
            f"Rejected packet from seal {seal_id}: "
            "AES-CCM authentication failed."
        )
        return None

    # Expected plaintext:
    # Bytes 0-1: temperature * 10 (signed little-endian)
    # Byte 2:    tamper (0 or 1)
    # Bytes 3-4: vibration * 100 (unsigned little-endian)
    # Byte 5: movement type

    if len(plaintext) != 6:
        print("Rejected packet: incorrect plaintext length.")
        return None

    temperature_raw = int.from_bytes(
        plaintext[0:2],
        byteorder="little",
        signed=True
    )

    tamper_raw = plaintext[2]

    vibration_raw = int.from_bytes(
        plaintext[3:5],
        byteorder="little"
    )
    movement_type = plaintext[5]

    if tamper_raw not in (0, 1):
        print("Rejected packet: invalid tamper value.")
        return None

    if movement_type > 4:
        print("Rejected packet: invalid movement type.")
        return None

    temperature = temperature_raw / 10.0
    vibration = vibration_raw / 100.0

    print(
        f"Decryption successful: seal={seal_id}, "
        f"sequence={sequence}"
    )

    return {
        "seal_id": seal_id,
        "event_sequence": sequence,
        "temperature": temperature,
        "tamper": bool(tamper_raw),
        "vibration": vibration,
        "movement_type": movement_type,
    }


# --------------------------------------------------
# SIMULATION
# --------------------------------------------------

def simulated_packet():
    """Generate test sensor information without BLE."""

    simulated_packet.sequence = (
        getattr(simulated_packet, "sequence", 0) + 1
    )

    return {
        "seal_id": 1,
        "event_sequence": simulated_packet.sequence,
        "temperature": round(random.uniform(1.0, 10.0), 1),
        "tamper": random.choice([True, False]),
        "vibration": round(random.uniform(0.0, 3.05), 2),
        "movement_type": random.choice([0, 1]),
    }


# --------------------------------------------------
# BLE SCANNING
# --------------------------------------------------

async def scan_real_ble():
    """Scan for encrypted SmartSeal advertisements."""

    packets = []

    def detection_callback(device, advertisement):

        # Only accept the SmartSeal manufacturer ID.
        manufacturer_data = advertisement.manufacturer_data

        if MANUFACTURER_ID not in manufacturer_data:
            return

        payload = manufacturer_data[MANUFACTURER_ID]

        packet = parse_advertisement(payload)

        if packet is not None:
            packets.append(packet)

    scanner = BleakScanner(
        detection_callback=detection_callback
    )

    await scanner.start()

    try:
        await asyncio.sleep(SCAN_TIMEOUT)

    finally:
        await scanner.stop()

    if packets:
        # Return the newest valid packet observed.
        packet = packets[-1]

        print("Encrypted BLE packet successfully received.")
        print("Decoded packet:", packet)

        return packet

    print(
        "No valid encrypted SmartSeal packet received."
    )

    print(
        "Check that SmartSeal-XIAO is advertising "
        "the encrypted manufacturer packet."
    )

    return None


# --------------------------------------------------
# MAIN SCANNER FUNCTION
# --------------------------------------------------

def scan_ble():
    """Return one decoded sensor packet."""

    if SIMULATION_MODE:
        packet = simulated_packet()

        print("SIMULATED packet:", packet)

        return packet

    try:
        return asyncio.run(scan_real_ble())

    except RuntimeError as error:

        print(
            "Runtime error during BLE scanning:",
            error
        )

        return None

    except (BleakError, OSError) as error:

        print(
            "BLE scanning error:",
            error
        )

        return None

    except Exception as error:

        print(
            f"Unexpected scanner error: "
            f"{type(error).__name__}: {error}"
        )

        return None


if __name__ == "__main__":
    print("Scanner result:", scan_ble())
