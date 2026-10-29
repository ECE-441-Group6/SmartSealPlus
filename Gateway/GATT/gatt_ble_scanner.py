
"""Receive SmartSeal sensor packets over BLE GATT."""

import asyncio
import json
import os

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError


# These UUIDs are examples.
# They MUST match the services and characteristics in the XIAO firmware.

XIAO_DEVICE_NAME = "SmartSeal-XIAO"
SCAN_TIMEOUT = 5.0
PACKET_TIMEOUT = 15.0

# Service 1: sensor measurements
SENSOR_SERVICE_UUID = "12345678-1234-1234-1234-1234567890ab"
SENSOR_CHARACTERISTIC_UUID = "12345678-1234-1234-1234-1234567890ac"

# Service 2: communication and connection health
COMM_SERVICE_UUID = "12345678-1234-1234-1234-1234567890ad"
HEARTBEAT_CHARACTERISTIC_UUID = "12345678-1234-1234-1234-1234567890ae"
ACK_CHARACTERISTIC_UUID = "12345678-1234-1234-1234-1234567890af"

SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"



import json
import math

def decode_sensor_packet(data):
    
    """Decode and validate the JSON sensor packet."""
    try:
        packet = json.loads(data.decode("utf-8"))

        required_fields = {
            "seal_id",
            "event_sequence",
            "temperature",
            "tamper",
            "vibration",
        }

        if not isinstance(packet, dict):
            return None

        if not required_fields.issubset(packet):
            print("Sensor packet is missing required fields.")
            return None

        # These checks ensure the fields have the expected basic types.
        if (
            not isinstance(packet["seal_id"], int)
            or isinstance(packet["seal_id"], bool)
            or packet["seal_id"] < 1
        ):
            return None

        if (
            not isinstance(packet["event_sequence"], int)
            or isinstance(packet["event_sequence"], bool)
            or not 0 <= packet["event_sequence"] <= 0xFFFFFFFF
        ):
            return None

        if (
            not isinstance(packet["temperature"], (int, float))
            or isinstance(packet["temperature"], bool)
        ):
            return None

        if (
            not isinstance(packet["vibration"], (int, float))
            or isinstance(packet["vibration"], bool)
        ):
            return None

        if not isinstance(packet["tamper"], bool):
            return None

        return {
            "seal_id": packet["seal_id"],
            "event_sequence": packet["event_sequence"],
            "temperature": packet["temperature"],
            "tamper": packet["tamper"],
            "vibration": packet["vibration"],
        }

    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        print("Could not decode sensor packet.")
        return None

def extract_complete_json_packets(buffer):
    """Extract complete JSON objects from a buffer of BLE notifications."""
    packets = []

    while buffer:
        # Discard any bytes before the start of a JSON object.
        if buffer[0] != ord("{"):
            del buffer[0]
            continue

        depth = 0
        in_string = False
        escaped = False
        packet_end = None

        for i, byte in enumerate(buffer):
            char = chr(byte)

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1

                if depth == 0:
                    packet_end = i + 1
                    break

        # Wait for the remaining bytes if the JSON is incomplete.
        if packet_end is None:
            break

        packets.append(bytes(buffer[:packet_end]))
        del buffer[:packet_end]

    return packets

async def scan_real_ble():
    """Find the XIAO, connect, subscribe, and receive one sensor packet."""

    # Find a device advertising our sensor service.
    device = await BleakScanner.find_device_by_filter(
        lambda found_device, advertisement: (
            XIAO_DEVICE_NAME == (
                advertisement.local_name or found_device.name
            )
            and SENSOR_SERVICE_UUID.lower()
            in {
                uuid.lower()
                for uuid in (advertisement.service_uuids or [])
            }
        ),
        timeout=SCAN_TIMEOUT,
    )

    if device is None:
        print("SmartSeal XIAO not found during BLE scan.")
        return None

    print(f"Found XIAO: {device.name or device.address}")
    print("Connecting to XIAO GATT server...")

    sensor_queue = asyncio.Queue()
    heartbeat_queue = asyncio.Queue()

    async with BleakClient(device) as client:
        print("GATT connected:", client.is_connected)

        # Confirm the required characteristics exist.
        services = client.services

        required_uuids = {
            SENSOR_CHARACTERISTIC_UUID.lower(),
            HEARTBEAT_CHARACTERISTIC_UUID.lower(),
            ACK_CHARACTERISTIC_UUID.lower(),
        }

        available_uuids = {
            characteristic.uuid.lower()
            for service in services
            for characteristic in service.characteristics
        }

        missing = required_uuids - available_uuids
        if missing:
            raise BleakError(
                f"Required GATT characteristics not found: {missing}"
            )

        def on_sensor_notification(sender, data):
            """Called whenever the XIAO sends a sensor notification."""
            packet = decode_sensor_packet(bytes(data))

            if packet is not None:
                sensor_queue.put_nowait(packet)

        def on_heartbeat_notification(sender, data):
            """Called whenever the XIAO sends a heartbeat."""
            heartbeat = bytes(data)

            print(f"XIAO heartbeat received: {heartbeat.hex()}")

            heartbeat_queue.put_nowait(heartbeat)

        # Subscribe to both notification characteristics.
        await client.start_notify(
            SENSOR_CHARACTERISTIC_UUID,
            on_sensor_notification,
        )

        await client.start_notify(
            HEARTBEAT_CHARACTERISTIC_UUID,
            on_heartbeat_notification,
        )

        print("Subscribed to sensor and heartbeat notifications.")
        print("Waiting for a sensor packet...")

        try:
            # Wait for a valid sensor packet.
            packet = await asyncio.wait_for(
                sensor_queue.get(),
                timeout=PACKET_TIMEOUT,
            )

            print(f"Sensor packet received: {packet}")

            # Tell the XIAO which sensor event the Pi received.
            sequence = packet["event_sequence"]

            await client.write_gatt_char(
                ACK_CHARACTERISTIC_UUID,
                sequence.to_bytes(4, byteorder="little"),
                response=True,
            )

            print(f"Acknowledgment sent for event {sequence}.")

            return packet

        finally:
            await client.stop_notify(SENSOR_CHARACTERISTIC_UUID)
            await client.stop_notify(HEARTBEAT_CHARACTERISTIC_UUID)

    # The GATT connection closes when the async context exits.


def scan_ble():
    """Return one sensor packet for gateway_main.py."""

    if SIMULATION_MODE:
        from random import uniform, choice

        scan_ble.sequence = (
            getattr(scan_ble, "sequence", 0) + 1
        ) & 0xFFFFFFFF

        packet = {
            "seal_id": 1,
            "event_sequence": scan_ble.sequence,
            "temperature": round(uniform(1.0, 10.0), 1),
            "tamper": choice([True, False]),
            "vibration": round(uniform(0.0, 3.05), 2),
        }

        print(f"SIMULATED packet: {packet}")
        return packet

    try:
        return asyncio.run(scan_real_ble())

    except (BleakError, OSError, asyncio.TimeoutError) as error:
        print(f"BLE/GATT error: {error}")
        return None

    except RuntimeError as error:
        print(f"Runtime error during GATT scan: {error}")
        return None


if __name__ == "__main__":
    print("Scanner result:", scan_ble())
