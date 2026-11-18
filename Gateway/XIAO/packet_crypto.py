
"""AES-128-CCM decryption for SmartSeal BLE advertisements."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from Gateway.seal_keys import load_seal_keys


SEAL_KEYS = load_seal_keys()

MANUFACTURER_ID = 0x5353
MAGIC = 0xA5
PROTOCOL_VERSION = 4

HEADER_LENGTH = 3
SEQUENCE_LENGTH = 4
PLAINTEXT_LENGTH = 6
TAG_LENGTH = 8
PACKET_LENGTH = 21



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
    seal_crypto = SEAL_KEYS.get(seal_id)
    if seal_crypto is None:
        return None
    aes, nonce_prefix = seal_crypto

    sequence = int.from_bytes(payload[3:7], "little")

    # The sequence counter must never repeat for the same key.
    nonce = nonce_prefix + payload[3:7]

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
