# Converts incoming packet data into validated SmartSeal information.

from math import isfinite
from numbers import Real


def parse_packet(packet):
    try:
        if packet is None:
            raise ValueError("No packet received")

        seal_id = packet["seal_id"]
        event_sequence = packet["event_sequence"]
        temperature = packet["temperature"]
        vibration = packet["vibration"]

        # Validate the seal ID.
        if (
            not isinstance(seal_id, int)
            or isinstance(seal_id, bool)
            or seal_id < 1
        ):
            raise ValueError("Invalid seal ID")

        if (
            not isinstance(event_sequence, int)
            or isinstance(event_sequence, bool)
            or not 0 <= event_sequence <= 0xFFFFFFFF
        ):
            raise ValueError("Invalid event sequence")

        # Validate the temperature.
        if (
            not isinstance(temperature, Real)
            or isinstance(temperature, bool)
            or not isfinite(temperature)
        ):
            raise ValueError("Invalid temperature")

        # Tamper detection hardware is not currently installed.
        if (
            not isinstance(vibration, Real)
            or isinstance(vibration, bool)
            or not isfinite(vibration)
            or vibration < 0
        ):
            raise ValueError("Invalid vibration voltage")

        return {
            "seal_id": seal_id,
            "event_sequence": event_sequence,
            "temperature": temperature,
            "tamper": False,
            "vibration": vibration
        }

    except (KeyError, TypeError, ValueError) as error:
        print(f"Packet Error: {error}")
        return None