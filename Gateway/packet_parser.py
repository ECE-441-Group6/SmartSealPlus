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
        tamper = packet.get("tamper", False)
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
        if temperature is not None and (
            not isinstance(temperature, Real)
            or isinstance(temperature, bool)
            or not isfinite(temperature)
        ):
            raise ValueError("Invalid temperature")

        if (
            not isinstance(tamper, bool)
        ):
            raise ValueError("Invalid tamper status")

        if (
            not isinstance(vibration, (bool, Real))
            or not isfinite(vibration)
            or (not isinstance(vibration, bool) and vibration < 0)
        ):
            raise ValueError("Invalid vibration voltage")

        return {
            "seal_id": seal_id,
            "event_sequence": event_sequence,
            "temperature": temperature,
            "tamper": tamper,
            "vibration": vibration
        }

    except (KeyError, TypeError, ValueError) as error:
        print(f"Packet Error: {error}")
        return None