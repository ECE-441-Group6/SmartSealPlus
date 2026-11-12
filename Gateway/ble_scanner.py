
"""Receive and decrypt SmartSeal BLE advertisements."""

import base64
import binascii
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

def _load_key_configuration():
    """Load the shared nonce prefix and AES keys indexed by seal ID."""
    key_path = Path(
        os.getenv(
            "SMARTSEAL_KEY_REGISTRY",
            str(Path(__file__).with_name("keys.json")),
        )
    ).expanduser()
    try:
        with key_path.open(encoding="utf-8") as key_file:
            configuration = json.load(key_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not load SmartSeal key registry from {key_path}."
        ) from error

    if not isinstance(configuration, dict):
        raise RuntimeError(
            f"SmartSeal key registry {key_path} must contain a JSON object."
        )

    try:
        nonce_prefix = bytes.fromhex(
            configuration["SMARTSEAL_NONCE_PREFIX"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            "SMARTSEAL_NONCE_PREFIX must contain hexadecimal bytes."
        ) from error

    if len(nonce_prefix) != 9:
        raise RuntimeError(
            "SMARTSEAL_NONCE_PREFIX must be exactly 9 bytes "
            "(18 hexadecimal characters)."
        )

    ciphers = {}
    for seal_id, encoded_key in configuration.items():
        if not seal_id.isdecimal():
            continue

        try:
            key = base64.b64decode(encoded_key, validate=True)
        except (binascii.Error, TypeError, ValueError) as error:
            raise RuntimeError(
                f"Key for seal {seal_id} must be Base64 encoded."
            ) from error

        if not 1 <= int(seal_id) <= 255 or len(key) != 16:
            raise RuntimeError(
                f"Key for seal {seal_id} must identify a seal from 1 to 255 "
                "and contain exactly 16 bytes."
            )
        ciphers[int(seal_id)] = AESCCM(key, tag_length=8)

    legacy_key = configuration.get("SMARTSEAL_AES_KEY")
    if legacy_key is not None:
        try:
            legacy_key = bytes.fromhex(legacy_key)
            legacy_seal_id = int(
                configuration.get("SMARTSEAL_LEGACY_SEAL_ID", 1)
            )
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                "Legacy SmartSeal key configuration is invalid."
            ) from error

        if len(legacy_key) != 16 or not 1 <= legacy_seal_id <= 255:
            raise RuntimeError(
                "Legacy SmartSeal configuration must contain a 16-byte key "
                "and a seal ID from 1 to 255."
            )
        ciphers[legacy_seal_id] = AESCCM(legacy_key, tag_length=8)

    if not ciphers:
        raise RuntimeError(
            f"No per-seal AES keys were found in {key_path}."
        )

    return nonce_prefix, ciphers


NONCE_PREFIX, AES_BY_SEAL = _load_key_configuration()

AES_TAG_LENGTH = 8
MAGIC = 0xA5
PROTOCOL_VERSION = 3
EXPECTED_PACKET_LENGTH = 21


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

    seal_cipher = AES_BY_SEAL.get(seal_id)
    if seal_cipher is None:
        print(f"Rejected packet from unconfigured seal {seal_id}.")
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
        plaintext = seal_cipher.decrypt(
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
    ) & 0xFFFFFFFF

    return {
        "seal_id": 1,
        "event_sequence": simulated_packet.sequence,
        "temperature": round(random.uniform(-10.0, 40.0), 1),
        "tamper": random.choice([True, False]),
        "vibration": random.choice([0.0, 1.0]),
        "movement_type": random.randint(0, 4),
    }


# --------------------------------------------------
# BLE SCANNING
# --------------------------------------------------

async def scan_real_ble_packets():
    """Scan for the newest valid packet from each seal in range."""

    packets_by_seal = {}

    def detection_callback(device, advertisement):

        # Only accept the SmartSeal manufacturer ID.
        manufacturer_data = advertisement.manufacturer_data

        if MANUFACTURER_ID not in manufacturer_data:
            return

        payload = manufacturer_data[MANUFACTURER_ID]

        packet = parse_advertisement(payload)

        if packet is not None:
            packets_by_seal[packet["seal_id"]] = packet

    scanner = BleakScanner(
        detection_callback=detection_callback
    )

    await scanner.start()

    try:
        await asyncio.sleep(SCAN_TIMEOUT)

    finally:
        await scanner.stop()

    if packets_by_seal:
        packets = list(packets_by_seal.values())
        print(
            "Encrypted BLE packets received from seals:",
            ", ".join(str(packet["seal_id"]) for packet in packets),
        )
        return packets

    print(
        "No valid encrypted SmartSeal packet received."
    )

    print(
        "Check that SmartSeal-XIAO is advertising "
        "the encrypted manufacturer packet."
    )

    return []


async def scan_real_ble():
    """Return one decoded sensor packet for backward compatibility."""
    packets = await scan_real_ble_packets()
    return packets[-1] if packets else None


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


def scan_ble_packets():
    """Return the newest packet observed from each seal in one scan."""
    if SIMULATION_MODE:
        packet = simulated_packet()
        print("SIMULATED packet:", packet)
        return [packet]

    try:
        return asyncio.run(scan_real_ble_packets())
    except RuntimeError as error:
        print("Runtime error during BLE scanning:", error)
        return []
    except (BleakError, OSError) as error:
        print("BLE scanning error:", error)
        return []
    except Exception as error:
        print(
            f"Unexpected scanner error: "
            f"{type(error).__name__}: {error}"
        )
        return []


if __name__ == "__main__":
    print("Scanner result:", scan_ble_packets())
