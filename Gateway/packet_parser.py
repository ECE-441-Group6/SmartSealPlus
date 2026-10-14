# Converts raw BLE advertisement bytes into useful information such as seal ID, temperature, and tamper status.
from math import isfinite
from numbers import Real


def parse_packet(packet):
    # Reject malformed advertisements before they reach alerting or storage.
    try:
        seal_id = packet["seal_id"]
        temperature = packet["temperature"]
        tamper = packet["tamper"]
        vibration = packet["vibration"]

        if (
            not isinstance(seal_id, int)
            or isinstance(seal_id, bool)
            or seal_id < 1
            or not isinstance(temperature, Real)
            or isinstance(temperature, bool)
            or not isfinite(temperature)
            or not isinstance(tamper, bool)
            or not isinstance(vibration, bool)
        ):
            raise ValueError("invalid SmartSeal field type or value")

        return {
            "seal_id": seal_id,
            "temperature": temperature,
            "tamper": tamper,
            "vibration": vibration
        }

    except (KeyError, TypeError, ValueError) as error:
        # Invalid or incomplete advertisements are ignored by the main loop.
        print(f"Packet Error: {error}")
        return None