"""SmartSeal+ gateway with validation, idempotent storage, and delivery ACKs."""

import csv
import sqlite3
import time

if __package__:
    from .ble_scanner import scan_ble
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
    from ble_scanner import scan_ble
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


def run_gateway(interval=5, scanner=scan_ble):
    init_database()
    clear_event_history()
    print("SmartSeal+ gateway started.")
    print("Previous dashboard events cleared.")
    last_stale_check = 0.0

    try:
        while True:
            try:
                raw_packet = scanner()
                if raw_packet is None:
                    print("No sensor packet received; retrying BLE scan.")
                    continue

                packet = parse_packet(raw_packet)
                if packet is None:
                    print("Invalid sensor packet. Skipping...")
                    continue

                record_seen(packet)
                now = time.monotonic()
                if now - last_stale_check >= max(interval, 5):
                    for seal_id, last_seen in get_stale_seals(max(interval * 3, 15)):
                        print(
                            f"WARNING: seal {seal_id} stopped reporting; "
                            f"last seen {last_seen}"
                        )
                    last_stale_check = now

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
                                str(image_path(image_filename)), packet
                            )
                        except Exception as error:
                            print(f"AI analysis error: {error}")
                            ai_analysis = "Analysis unavailable."
                    else:
                        ai_analysis = "Alert detected; image unavailable."

                update_event_artifacts(packet, image_filename, ai_analysis)

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
        try:
            archive_path = archive_events()
            print(f"Gateway event archive saved: {archive_path}")
        except (OSError, sqlite3.Error, csv.Error) as error:
            print(f"ERROR: Could not archive gateway events: {error}")


if __name__ == "__main__":
    run_gateway()
