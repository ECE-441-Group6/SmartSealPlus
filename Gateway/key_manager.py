"""Secure key management for SmartSeal+ devices."""

import os
import re
import secrets


KEY_SIZE_BYTES = 32
KEY_SIZE_HEX = KEY_SIZE_BYTES * 2


def generate_secret_key():
    """Generate a cryptographically secure 256-bit key."""
    return secrets.token_hex(KEY_SIZE_BYTES)


def get_device_key(seal_id):
    """
    Load a device-specific HMAC key from an environment variable.

    Example:
        SMARTSEAL_KEY_1
    """

    if isinstance(seal_id, bool) or not isinstance(seal_id, int):
        raise ValueError("Seal ID must be a positive integer.")

    if seal_id <= 0:
        raise ValueError("Seal ID must be a positive integer.")

    variable_name = f"SMARTSEAL_KEY_{seal_id}"

    key_hex = os.environ.get(variable_name)

    if key_hex is None:
        raise ValueError(
            f"Missing authentication key for seal {seal_id}."
        )

    if not re.fullmatch(r"[0-9a-fA-F]{64}", key_hex):
        raise ValueError(
            f"Invalid authentication key for seal {seal_id}."
        )

    return bytes.fromhex(key_hex)