"""HMAC-SHA256 message authentication for SmartSeal+."""

import hashlib
import hmac
import json


def canonical_packet(packet):
    """Convert sensor data into deterministic bytes."""
    fields = (
        "seal_id",
        "event_sequence",
        "temperature",
        "tamper",
        "vibration",
    )

    data = {field: packet[field] for field in fields}

    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def generate_hmac(packet, secret_key):
    """Generate an authentication tag for a sensor packet."""
    message = canonical_packet(packet)

    return hmac.new(
        secret_key,
        message,
        hashlib.sha256,
    ).hexdigest()


def verify_hmac(packet, secret_key, received_hmac):
    """Verify a packet's authentication tag."""
    if not isinstance(received_hmac, str):
        return False

    try:
        expected_hmac = generate_hmac(packet, secret_key)
    except (KeyError, TypeError, ValueError):
        return False

    return hmac.compare_digest(
        expected_hmac,
        received_hmac,
    )