"""SmartSeal+ gateway with validation, idempotent storage, and delivery ACKs."""

import time

if __package__:
    from .ble_scanner import scan_ble
    from .packet_parser import parse_packet
    from .database import (
        get_stale_seals,
        init_database,
        insert_event,
        is_stale_sequence,
        record_seen,
    )
    from .alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
    from .ai_analyzer import analyze_image
    from .camera_manager import capture_image
    from .image_storage import image_path
else:
    from ble_scanner import scan_ble
    from packet_parser import parse_packet
    from database import (
        get_stale_seals,
        init_database,
        insert_event,
        is_stale_sequence,
        record_seen,
    )
    from alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
    from ai_analyzer import analyze_image
    from camera_manager import capture_image
    from image_storage import image_path


def run_gateway(interval=5, scanner=scan_ble):
    init_database()
    print("SmartSeal+ gateway started.")
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

                if is_stale_sequence(packet):
                    print(
                        f"Stale event rejected: seal={packet['seal_id']} "
                        f"seq={packet['event_sequence']}"
                    )
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

                alerts = process_alerts(packet)
                temperature_out_of_range = (
                    packet["temperature"] < TEMP_LOW
                    or packet["temperature"] > TEMP_HIGH
                )
                alert_triggered = (
                    packet["tamper"]
                    or packet["vibration"]
                    or temperature_out_of_range
                )

                image_filename = None
                ai_analysis = "No issues detected."
                if alert_triggered:
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

                try:
                    inserted = insert_event(packet, image_filename, ai_analysis)
                    status = "recorded" if inserted else "duplicate ignored"
                    print(
                        f"Event {status}: seal={packet['seal_id']} "
                        f"seq={packet['event_sequence']}"
                    )
                    acknowledge = raw_packet.get("_acknowledge")
                    if acknowledge is not None:
                        acknowledge()
                        print(
                            f"ACK transmitted: seal={packet['seal_id']} "
                            f"seq={packet['event_sequence']}"
                        )
                except Exception as error:
                    print(f"Database write/ACK suppressed: {error}")

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
        print("\nSmartSeal+ gateway stopped safely.")


if __name__ == "__main__":
    run_gateway()
