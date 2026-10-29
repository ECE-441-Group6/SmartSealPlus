
"""SmartSeal+ gateway with persistent BLE GATT subscriptions."""

import asyncio
import csv
import sqlite3
import time

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

if __package__:
    from .gatt_ble_scanner import (
        XIAO_DEVICE_NAME,
        SCAN_TIMEOUT,
        SENSOR_SERVICE_UUID,
        SENSOR_CHARACTERISTIC_UUID,
        COMM_SERVICE_UUID,
        HEARTBEAT_CHARACTERISTIC_UUID,
        ACK_CHARACTERISTIC_UUID,
        decode_sensor_packet,
        extract_complete_json_packets,
    )
    from .packet_parser import parse_packet
    from .database import (
        archive_events,
        clear_event_history,
        get_stale_seals,
        init_database,
        insert_event,
        record_seen,
        update_event_artifacts,
    )
    from .alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
    from .ai_analyzer import analyze_image
    from .camera_manager import capture_image
    from .image_storage import image_path
else:
    from gatt_ble_scanner import (
        XIAO_DEVICE_NAME,
        SCAN_TIMEOUT,
        SENSOR_SERVICE_UUID,
        SENSOR_CHARACTERISTIC_UUID,
        COMM_SERVICE_UUID,
        HEARTBEAT_CHARACTERISTIC_UUID,
        ACK_CHARACTERISTIC_UUID,
        decode_sensor_packet,
        extract_complete_json_packets,
    )
    from packet_parser import parse_packet
    from database import (
        archive_events,
        clear_event_history,
        get_stale_seals,
        init_database,
        insert_event,
        record_seen,
        update_event_artifacts,
    )
    from alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
    from ai_analyzer import analyze_image
    from camera_manager import capture_image
    from image_storage import image_path


HEARTBEAT_TIMEOUT = 15.0
RECONNECT_DELAY = 3.0


def find_smartseal(device, advertisement):
    """Identify the XIAO by its advertised name or sensor service UUID."""

    name = advertisement.local_name or device.name or ""

    advertised_services = {
        uuid.lower()
        for uuid in (advertisement.service_uuids or [])
    }

    return (
        name == XIAO_DEVICE_NAME
        or SENSOR_SERVICE_UUID.lower() in advertised_services
    )


def process_sensor_packet(raw_packet):
    """Validate, store, and process one sensor event."""

    packet = parse_packet(raw_packet)

    if packet is None:
        print("Invalid sensor packet. Skipping...")
        return None

    # Preserve the actual tamper value decoded from the GATT packet.
    # decode_sensor_packet() already validates that it is a boolean.
    packet["tamper"] = raw_packet["tamper"]

    record_seen(packet)

    inserted = insert_event(packet)
    status = "recorded" if inserted else "duplicate ignored"

    print(
        f"Event {status}: seal={packet['seal_id']} "
        f"seq={packet['event_sequence']}"
    )

    alerts = process_alerts(packet)

    temperature_out_of_range = (
        packet["temperature"] < TEMP_LOW
        or packet["temperature"] > TEMP_HIGH
    )

    capture_triggered = packet["tamper"] or packet["vibration"]

    image_filename = None

    ai_analysis = (
        "Temperature out of bounds; image capture skipped."
        if temperature_out_of_range and not capture_triggered
        else "No issues detected."
    )

    if capture_triggered:
        try:
            image_filename = capture_image(packet)
        except Exception as error:
            print(f"Camera error: {error}")

        if image_filename:
            try:
                ai_analysis = analyze_image(
                    str(image_path(image_filename)),
                    packet,
                )
            except Exception as error:
                print(f"AI analysis error: {error}")
                ai_analysis = "Analysis unavailable."
        else:
            ai_analysis = "Alert detected; image unavailable."

    update_event_artifacts(
        packet,
        image_filename,
        ai_analysis,
    )

    print("\nPacket Received")
    print(packet)

    for alert in alerts:
        print("ALERT:", alert)

    print("Analysis:", ai_analysis)

    return packet


async def run_connected_session():
    """Connect once and continuously receive GATT notifications."""

    print("Searching for SmartSeal XIAO...")

    device = await BleakScanner.find_device_by_filter(
        find_smartseal,
        timeout=SCAN_TIMEOUT,
    )

    if device is None:
        print("XIAO not found. Will retry.")
        return

    print(f"Found XIAO: {device.name or device.address}")
    print("Connecting...")

    # Queue entries distinguish sensor events from heartbeat messages.
    notification_queue = asyncio.Queue()
    sensor_buffer = bytearray()

    async with BleakClient(device, timeout=10.0) as client:
        print("GATT connected.")

        services = client.services

        required_characteristics = {
            SENSOR_CHARACTERISTIC_UUID.lower(),
            HEARTBEAT_CHARACTERISTIC_UUID.lower(),
            ACK_CHARACTERISTIC_UUID.lower(),
        }

        available_characteristics = {
            characteristic.uuid.lower()
            for service in services
            for characteristic in service.characteristics
        }

        missing = required_characteristics - available_characteristics

        if missing:
            raise BleakError(
                f"XIAO is missing required characteristics: {missing}"
            )

        # Track the most recent heartbeat using a monotonic clock.
        heartbeat_state = {
            "last_received": time.monotonic(),
            "received_any": False,
        }
        
        
        def sensor_callback(sender, data):
            """Reassemble BLE fragments before decoding sensor packets."""

            sensor_buffer.extend(bytes(data))

            for raw_data in extract_complete_json_packets(sensor_buffer):
                print(f"Complete JSON received: {raw_data!r}")

                raw_packet = decode_sensor_packet(raw_data)

                if raw_packet is not None:
                    notification_queue.put_nowait(
                        ("sensor", raw_packet)
                    )
                else:
                    print("Invalid complete sensor packet.")
        

        def heartbeat_callback(sender, data):
            """Record that the XIAO is still communicating."""

            heartbeat_state["last_received"] = time.monotonic()
            heartbeat_state["received_any"] = True

            notification_queue.put_nowait(
                ("heartbeat", bytes(data))
            )

        await client.start_notify(
            SENSOR_CHARACTERISTIC_UUID,
            sensor_callback,
        )

        await client.start_notify(
            HEARTBEAT_CHARACTERISTIC_UUID,
            heartbeat_callback,
        )

        print("Subscribed to sensor notifications.")
        print("Subscribed to heartbeat notifications.")
        print("Waiting for live sensor data...")

        last_stale_check = time.monotonic()

        try:
            while client.is_connected:
                # Check the heartbeat regularly, even when no sensor
                # notifications are arriving.
                try:
                    kind, data = await asyncio.wait_for(
                        notification_queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    kind, data = None, None

                if kind == "heartbeat":
                    print(f"Heartbeat received: {data.hex()}")

                elif kind == "sensor":
                    packet = process_sensor_packet(data)

                    if packet is not None:
                        # Acknowledge the event sequence number only
                        # after processing the received packet.
                        sequence = packet["event_sequence"]

                        await client.write_gatt_char(
                            ACK_CHARACTERISTIC_UUID,
                            sequence.to_bytes(
                                4,
                                byteorder="little",
                            ),
                            response=True,
                        )

                        print(
                            f"ACK sent for event {sequence}."
                        )

                now = time.monotonic()

                if (
                    now - last_stale_check
                    >= max(5.0, HEARTBEAT_TIMEOUT / 2)
                ):
                    for seal_id, last_seen in get_stale_seals(
                        HEARTBEAT_TIMEOUT
                    ):
                        print(
                            f"WARNING: seal {seal_id} stopped reporting; "
                            f"last seen {last_seen}"
                        )

                    last_stale_check = now

                heartbeat_age = (
                    now - heartbeat_state["last_received"]
                )

                if heartbeat_age >= HEARTBEAT_TIMEOUT:
                    print(
                        "WARNING: No heartbeat received for "
                        f"{heartbeat_age:.1f} seconds."
                    )
                    print("Closing session and reconnecting.")
                    break

        finally:
            # Stop subscriptions before leaving the connection session.
            try:
                await client.stop_notify(
                    SENSOR_CHARACTERISTIC_UUID
                )
            except (BleakError, OSError):
                pass

            try:
                await client.stop_notify(
                    HEARTBEAT_CHARACTERISTIC_UUID
                )
            except (BleakError, OSError):
                pass

    print("GATT session ended.")


async def run_gateway():
    """Initialize storage and maintain a persistent GATT connection."""

    init_database()
    clear_event_history()

    print("SmartSeal+ gateway started.")
    print("Previous dashboard events cleared.")

    try:
        while True:
            try:
                await run_connected_session()

            except asyncio.CancelledError:
                raise

            except (
                BleakError,
                OSError,
                asyncio.TimeoutError,
                RuntimeError,
            ) as error:
                print(f"BLE/GATT connection error: {error}")

            print(
                f"Retrying connection in {RECONNECT_DELAY} seconds..."
            )

            await asyncio.sleep(RECONNECT_DELAY)

    except KeyboardInterrupt:
        print("\nSmartSeal+ gateway stopped.")

    finally:
        try:
            archive_path = archive_events()
            print(f"Gateway event archive saved: {archive_path}")

        except (OSError, sqlite3.Error, csv.Error) as error:
            print(
                f"ERROR: Could not archive gateway events: {error}"
            )


if __name__ == "__main__":
    try:
        asyncio.run(run_gateway())
    except KeyboardInterrupt:
        pass
