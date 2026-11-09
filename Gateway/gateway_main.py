
"""SmartSeal+ gateway with validation, atomic storage, and event archiving."""

import csv
import sqlite3
import time

if __package__:
    from . import database
    from .replay_protection import ReplayProtector
    from .ble_scanner import scan_ble
    from .packet_parser import parse_packet
    from .key_registry import load_key_registry
    from .database import (
        archive_events,
        get_stale_seals,
        init_database,
        update_event_artifacts,
    )
    from .alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
    from .ai_analyzer import analyze_image
    from .camera_manager import capture_image
    from .image_storage import image_path
else:
    import database
    from replay_protection import ReplayProtector
    from ble_scanner import scan_ble
    from packet_parser import parse_packet
    from key_registry import load_key_registry
    from database import (
        archive_events,
        get_stale_seals,
        init_database,
        update_event_artifacts,
    )
    from alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
    from ai_analyzer import analyze_image
    from camera_manager import capture_image
    from image_storage import image_path


def run_gateway(interval=5, scanner=scan_ble):
    """Run the SmartSeal+ gateway and process incoming sensor events."""

    # Initialize the security keys and database.
    load_key_registry()
    init_database()

    # Initialize persistent replay-protection storage.
    # The atomic storage function uses the same security_sequences table.
    ReplayProtector(db_path=database.DB_NAME)

    # Preserve event history across gateway restarts.
    print("SmartSeal+ gateway started.")
    print("Previous event history preserved.")

    last_stale_check = 0.0

    try:
        while True:
            try:
                # Receive the next sensor packet.
                raw_packet = scanner()

                if raw_packet is None:
                    print("No sensor packet received; retrying BLE scan.")
                    continue

                # Parse and validate the packet structure.
                packet = parse_packet(raw_packet)

                if packet is None:
                    print("Invalid sensor packet. Skipping...")
                    continue

                # Atomically check replay sequence and store the event.
                # The default BLE scanner authenticates encrypted packets
                # before passing them to this processing stage.
                accepted, reason = database.accept_and_store_event(
                    packet
                )

                if not accepted:
                    print(f"Rejected packet: {reason}")
                    continue

                # Check whether any seals have stopped reporting.
                now = time.monotonic()

                if now - last_stale_check >= max(interval, 5):
                    for seal_id, last_seen in get_stale_seals(
                        max(interval * 3, 15)
                    ):
                        print(
                            f"WARNING: seal {seal_id} stopped reporting; "
                            f"last seen {last_seen}"
                        )

                    last_stale_check = now

                print(
                    f"Event recorded: seal={packet['seal_id']} "
                    f"seq={packet['event_sequence']}"
                )

                # Process temperature, tamper, and vibration alerts.
                alerts = process_alerts(packet)

                temperature_out_of_range = (
                    packet["temperature"] is not None
                    and (
                        packet["temperature"] < TEMP_LOW
                        or packet["temperature"] > TEMP_HIGH
                    )
                )

                capture_triggered = (
                    packet["tamper"] or packet["vibration"]
                )

                image_filename = None

                ai_analysis = (
                    "Temperature out of bounds; image capture skipped."
                    if temperature_out_of_range and not capture_triggered
                    else "No issues detected."
                )

                # Capture and analyze images when a physical event occurs.
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
                        ai_analysis = (
                            "Alert detected; image unavailable."
                        )

                # Update the stored event with camera/AI evidence.
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

                time.sleep(interval)

            except Exception as error:
                print(f"Gateway processing error: {error}")
                time.sleep(interval)

    except KeyboardInterrupt:
        print("\nSmartSeal+ gateway stopped.")

    finally:
        # Archive recorded events during gateway shutdown.
        try:
            archive_path = archive_events()

            print(
                f"Gateway event archive saved: {archive_path}"
            )

        except (OSError, sqlite3.Error, csv.Error) as error:
            print(
                f"ERROR: Could not archive gateway events: {error}"
            )


if __name__ == "__main__":
    run_gateway()
