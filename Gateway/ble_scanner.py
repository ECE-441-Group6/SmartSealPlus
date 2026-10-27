"""Receive SmartSeal sensor packets over BLE advertisements."""

import asyncio
import os
import random
import re

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

MANUFACTURER_ID = 0x5353
ESP_DEVICE_NAMES = {"SmartSeal-01"}
XIAO_DEVICE_NAME = "SmartSeal-XIAO"
XIAO_CHARACTERISTIC_UUID = "12345678-1234-1234-1234-1234567890ae"
ESP32_ACK_CHARACTERISTIC_UUID = "12345678-1234-1234-1234-1234567890ad"


def ack_message(packet):
    return f"ACK:S:{packet['seal_id']},E:{packet['event_sequence']}".encode("ascii")


def ack_matches(packet, acknowledgement):
    if isinstance(acknowledgement, (bytes, bytearray)):
        acknowledgement = acknowledgement.decode("ascii", errors="ignore")
    return acknowledgement == ack_message(packet).decode("ascii")


SCAN_TIMEOUT = 5.0
SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"


def parse_advertisement(payload):
    """Convert an ESP32 or XIAO manufacturer payload into a gateway packet."""
    if payload is None:
        return None

    if isinstance(payload, (bytes, bytearray)):
        # Bleak normally removes the company ID. Accept it too for backends
        # that expose the raw manufacturer field.
        if payload.startswith(b"\x53\x53"):
            payload = payload[2:]
        if len(payload) == 12 and payload[0] == 0xA5 and payload[1] == 1:
            sequence = int.from_bytes(payload[3:7], "little")
            temperature = int.from_bytes(
                payload[7:9], "little", signed=True
            ) / 10.0
            vibration = int.from_bytes(payload[10:12], "little") / 100.0
            return {
                "seal_id": payload[2],
                "event_sequence": sequence,
                "temperature": temperature,
                "tamper": bool(payload[9]),
                "vibration": vibration,
            }
        payload = payload.decode("ascii", errors="ignore")

    match = re.fullmatch(
        r"S:(\d+),E:(\d+),T:([-+]?\d+(?:\.\d+)?),A:([01]),V:([-+]?\d+(?:\.\d+)?)",
        payload.strip("\x00 \r\n"),
    )
    if not match:
        return None

    seal_id, event_sequence, temperature, tamper, vibration_voltage = match.groups()
    return {
        "seal_id": int(seal_id),
        "event_sequence": int(event_sequence),
        "temperature": float(temperature),
        "tamper": tamper == "1",
        "vibration": float(vibration_voltage),
    }


def parse_xiao_message(payload):
    """Parse the sensor packet exposed by the XIAO GATT characteristic."""
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("ascii", errors="ignore")
    return parse_advertisement(payload)


def simulated_packet():
    """Generate a packet when a BLE adapter or ESP32 is not available."""
    simulated_packet.sequence = (getattr(simulated_packet, "sequence", 0) + 1) & 0xFFFFFFFF
    return {
        "seal_id": 1,
        "event_sequence": simulated_packet.sequence,
        "temperature": round(random.uniform(1.0, 10.0), 1),
        "tamper": random.choice([True, False]),
        "vibration": round(random.uniform(0.0, 3.05), 2),
    }


async def scan_real_ble():
    """Scan ESP advertisements and read a packet from the XIAO GATT service."""
    packets = []
    packet_devices = []
    xiao_device = None

    def detection_callback(device, advertisement):
        nonlocal xiao_device
        device_name = advertisement.local_name or device.name or ""
        service_uuids = {
            uuid.lower() for uuid in (advertisement.service_uuids or [])
        }
        is_xiao = (
            device_name == XIAO_DEVICE_NAME
            or "0000180f-0000-1000-8000-00805f9b34fb" in service_uuids
            or "180f" in service_uuids
        )
        if is_xiao:
            xiao_device = device

        payload = advertisement.manufacturer_data.get(MANUFACTURER_ID)
        if payload is None or is_xiao:
            return

        # The device name may be placed in a scan response or omitted when the
        # advertisement is full. The company ID and payload are the reliable
        # protocol identifiers, so do not require the name here.
        packet = parse_advertisement(payload)
        if packet is not None:
            packets.append(packet)
            packet_devices.append(device)
        else:
            print(
                "Ignoring invalid manufacturer payload from "
                f"{device.name or 'unnamed'}: {payload!r}"
            )

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    try:
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        await scanner.stop()

    if xiao_device is None and not packets:
        try:
            xiao_device = await BleakScanner.find_device_by_name(
                XIAO_DEVICE_NAME,
                timeout=SCAN_TIMEOUT,
            )
        except (BleakError, OSError, asyncio.TimeoutError) as error:
            print(f"XIAO BLE discovery error: {error}")

    if xiao_device is not None:
        try:
            async with BleakClient(xiao_device) as client:
                payload = await client.read_gatt_char(XIAO_CHARACTERISTIC_UUID)
            packet = parse_xiao_message(payload)
            if packet is not None:
                print(f"XIAO BLE packet received: {packet}")
                packet["_acknowledge"] = lambda: asyncio.run(
                    write_ack(xiao_device, XIAO_CHARACTERISTIC_UUID, packet)
                )
                return packet
            print("XIAO BLE characteristic did not contain a sensor packet.")
        except (BleakError, OSError, asyncio.TimeoutError) as error:
            print(f"XIAO BLE read error: {error}")

    if packets:
        packet = packets[-1]
        print(f"BLE packet received: {packet}")
        device = packet_devices[-1]
        packet["_acknowledge"] = lambda: asyncio.run(
            write_ack(device, ESP32_ACK_CHARACTERISTIC_UUID, packet)
        )
        return packet

    print(
        "No valid BLE packet received from "
        f"{', '.join(sorted(ESP_DEVICE_NAMES | {XIAO_DEVICE_NAME}))}."
    )
    print(
        "Check that the XIAO is advertising and that the integrated sketch "
        "is uploaded; press D4 to start live sensor updates."
    )
    return None


async def write_ack(device, characteristic_uuid, packet):
    """Write an identity-bound ACK after the gateway commits the event."""
    acknowledgement = ack_message(packet)
    last_error = None
    for attempt in range(2):
        try:
            async with BleakClient(device) as client:
                await client.write_gatt_char(
                    characteristic_uuid,
                    acknowledgement,
                    response=True,
                )
            return
        except (BleakError, OSError, asyncio.TimeoutError) as error:
            last_error = error
            if attempt == 0:
                await asyncio.sleep(0.2)
    raise last_error


def scan_ble():
    """Return one ESP32 packet, using simulation only when explicitly enabled."""

    if SIMULATION_MODE:
        packet = simulated_packet()
        print(f"SIMULATED packet: {packet}")
        return packet

    try:
        return asyncio.run(scan_real_ble())

    except RuntimeError as error:
        if "asyncio.run() cannot be called" in str(error):
            print(f"ASYNCIO EVENT LOOP ERROR: {error}")
        else:
            print(f"RUNTIME ERROR DURING BLE SCAN: {error}")
        return None

    except Exception as error:
        print(f"BLE SCANNING ERROR: {type(error).__name__}: {error}")
        return None


if __name__ == "__main__":
    print("Scanner result:", scan_ble())
