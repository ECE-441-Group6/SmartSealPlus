
"""AES-128-CCM decryption for SmartSeal BLE advertisements."""

from cryptography.hazmat.primitives.ciphers.aead import AESCCM

# Replace with the NEW 16-byte key provisioned to the XIAO.
# Store this in a private configuration file, not GitHub.
ENCRYPTION_KEY = bytes.fromhex(
    "00112233445566778899aabbccddeeff"
)

# Replace with the matching 9-byte device-specific prefix.
NONCE_PREFIX = bytes.fromhex(
    "102030405060708090"
)

MANUFACTURER_ID = 0x5353
MAGIC = 0xA5
PROTOCOL_VERSION = 2

HEADER_LENGTH = 3
SEQUENCE_LENGTH = 4
PLAINTEXT_LENGTH = 5
TAG_LENGTH = 8
PACKET_LENGTH = 20

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
    nonce = NONCE_PREFIX + sequence.to_bytes(4, "big")

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

    if plaintext[2] not in (0, 1):
        return None

    return {
        "seal_id": seal_id,
        "event_sequence": sequence,
        "temperature": temperature_raw / 10.0,
        "tamper": tamper,
        "vibration": vibration_raw / 100.0,
    }
