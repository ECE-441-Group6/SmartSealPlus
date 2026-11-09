
"""AES-128-CCM decryption for SmartSeal BLE advertisements."""

import json
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESCCM


def _load_hex_secret(name, length):
    """Load a fixed-length hexadecimal secret from the local key file."""
    key_path = Path(__file__).parents[1] / "keys.json"
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


ENCRYPTION_KEY = _load_hex_secret("SMARTSEAL_AES_KEY", 16)
NONCE_PREFIX = _load_hex_secret("SMARTSEAL_NONCE_PREFIX", 9)

MANUFACTURER_ID = 0x5353
MAGIC = 0xA5
PROTOCOL_VERSION = 3

HEADER_LENGTH = 3
SEQUENCE_LENGTH = 4
PLAINTEXT_LENGTH = 6
TAG_LENGTH = 8
PACKET_LENGTH = 21

aes = AESCCM(ENCRYPTION_KEY, tag_length=TAG_LENGTH)


def decrypt_advertisement(payload):
    """Authenticate and decrypt one SmartSeal manufacturer payload."""

    if not isinstance(payload, (bytes, bytearray)):
        return None

    payload = bytes(payload)

    # Bleak manufacturer_data normally excludes the company ID.
    # Accept the raw company ID prefix as well.
    if payload.startswith(b"\x53\x53"):
        payload = payload[2:]

    if len(payload) != PACKET_LENGTH:
        return None

    if payload[0] != MAGIC or payload[1] != PROTOCOL_VERSION:
        return None

    seal_id = payload[2]
    if seal_id < 1:
        return None

    sequence = int.from_bytes(payload[3:7], "little")

    # The sequence counter must never repeat for the same key.
    nonce = NONCE_PREFIX + payload[3:7]

    # Authenticate the visible header and sequence number.
    aad = payload[:7]

    ciphertext_and_tag = payload[7:]

    try:
        plaintext = aes.decrypt(nonce, ciphertext_and_tag, aad)
    except Exception:
        print("Rejected BLE packet: authentication failed.")
        return None

    if len(plaintext) != PLAINTEXT_LENGTH:
        return None

    temperature_raw = int.from_bytes(
        plaintext[0:2], "little", signed=True
    )
    tamper = bool(plaintext[2])
    vibration_raw = int.from_bytes(plaintext[3:5], "little")
    movement_type = plaintext[5]

    if plaintext[2] not in (0, 1):
        return None
    if movement_type > 4:
        return None

    return {
        "seal_id": seal_id,
        "event_sequence": sequence,
        "temperature": temperature_raw / 10.0,
        "tamper": tamper,
        "vibration": vibration_raw / 100.0,
        "movement_type": movement_type,
    }
