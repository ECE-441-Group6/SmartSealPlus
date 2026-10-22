# Converts incoming packet data into validated SmartSeal information.

from math import isfinite
from numbers import Real


def parse_packet(packet):
    try:
        if packet is None:
            raise ValueError("No packet received")

        seal_id = packet["seal_id"]
        temperature = packet["temperature"]
        tamper = packet["tamper"]
        vibration = packet["vibration"]

        # Validate the seal ID.
        if (
            not isinstance(seal_id, int)
            or isinstance(seal_id, bool)
            or seal_id < 1
        ):
            raise ValueError("Invalid seal ID")

        # Validate the temperature.
        if (
            not isinstance(temperature, Real)
            or isinstance(temperature, bool)
            or not isfinite(temperature)
        ):
            raise ValueError("Invalid temperature")

        # Validate tamper and vibration states.
        if not isinstance(tamper, bool):
            raise ValueError("Invalid tamper status")

        if not isinstance(vibration, bool):
            raise ValueError("Invalid vibration status")

        return {
            "seal_id": seal_id,
            "temperature": temperature,
            "tamper": tamper,
            "vibration": vibration
        }

    except (KeyError, TypeError, ValueError) as error:
        print(f"Packet Error: {error}")
        return None