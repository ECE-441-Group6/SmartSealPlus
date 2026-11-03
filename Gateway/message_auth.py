"""HMAC-SHA256 message authentication for SmartSeal+."""

import hashlib
import hmac
import math


def canonical_packet(packet):
    """Create a fixed authentication message shared with the XIAO firmware."""

    seal_id = packet["seal_id"]
    sequence = packet["event_sequence"]
    temperature = packet["temperature"]
    tamper = packet["tamper"]
    vibration = packet["vibration"]

    # Validate seal ID.
    if type(seal_id) is not int or not 0 < seal_id <= 0xFFFFFFFF:
        raise ValueError("Invalid seal ID")

    # Validate event sequence.
    if type(sequence) is not int or not 0 <= sequence <= 0xFFFFFFFF:
        raise ValueError("Invalid event sequence")

    # Validate tamper status.
    if type(tamper) is not bool:
        raise ValueError("Invalid tamper value")

    # Validate temperature.
    if type(temperature) not in (int, float):
        raise ValueError("Invalid temperature")

    if not math.isfinite(temperature):
        raise ValueError("Invalid temperature")

    # Validate vibration.
    if type(vibration) not in (int, float):
        raise ValueError("Invalid vibration")

    if not math.isfinite(vibration) or vibration < 0:
        raise ValueError("Invalid vibration")

    # Generate a consistent message format for authentication.
    message = (
        f"seal_id={seal_id}\n"
        f"event_sequence={sequence}\n"
        f"temperature={temperature:.2f}\n"
        f"tamper={'true' if tamper else 'false'}\n"
        f"vibration={vibration:.3f}"
    )

    return message.encode("ascii")


def generate_hmac(packet, secret_key):
    """Generate an HMAC-SHA256 authentication tag for a sensor packet."""

    message = canonical_packet(packet)

    return hmac.new(
        secret_key,
        message,
        hashlib.sha256,
    ).hexdigest()


def verify_hmac(packet, secret_key, received_hmac):
    """Verify a packet's HMAC-SHA256 authentication tag."""

    if not isinstance(received_hmac, str):
        return False

    try:
        expected_hmac = generate_hmac(packet, secret_key)

    except (KeyError, TypeError, ValueError, OverflowError):
        return False

    return hmac.compare_digest(
        expected_hmac,
        received_hmac,
    )