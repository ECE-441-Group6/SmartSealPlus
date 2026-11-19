"""SmartSeal+ gateway with validation, idempotent storage, and delivery ACKs."""

import csv
import os
import queue
import sqlite3
import threading
import time

if __package__:
    from .ble_scanner import scan_ble
    from .packet_parser import parse_packet
    from .database import (
        archive_events,
        clear_event_history_all,
        get_stale_seals,
        init_database,
        accept_event,
        update_event_artifacts,
    )
    from .alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
    from .ai_analyzer import analyze_image
    from .camera_manager import capture_image
    from .image_storage import image_path
    from .gps_tracker import GPSLocationTracker
else:
    from ble_scanner import scan_ble
    from packet_parser import parse_packet
    from database import (
        archive_events,
        clear_event_history_all,
        get_stale_seals,
        init_database,
        accept_event,
        update_event_artifacts,
    )
    from alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
    from ai_analyzer import analyze_image
    from camera_manager import capture_image
    from image_storage import image_path
    from gps_tracker import GPSLocationTracker


def _artifact_worker(artifact_queue):
    """Capture and analyze alert images without blocking BLE scanning."""
    while True:
        item = artifact_queue.get()
        try:
            if item is None:
                return

            packet = item
            image_filename = None
            try:
                image_filename = capture_image(packet)
            except Exception as error:
                print(f"Camera error for seal {packet['seal_id']}: {error}")

            if image_filename:
                try:
                    ai_analysis = analyze_image(
                        str(image_path(image_filename)), packet
                    )
                except Exception as error:
                    print(f"AI analysis error for seal {packet['seal_id']}: {error}")
                    ai_analysis = "Analysis unavailable."
            else:
                ai_analysis = "Alert detected; image unavailable."

            update_event_artifacts(packet, image_filename, ai_analysis)
            print(
                f"Background image analysis complete: seal={packet['seal_id']} "
                f"seq={packet['event_sequence']} — {ai_analysis}"
            )
        except Exception as error:
            print(f"Background image processing error: {error}")
        finally:
            artifact_queue.task_done()


def run_gateway(interval=5, scanner=scan_ble):
    init_database()
    gps_tracker = None
    if os.getenv("SMARTSEAL_SIMULATION", "0") != "1":
        gps_tracker = GPSLocationTracker()
        gps_tracker.start()

    # Recover readings left in the live table if the previous gateway process
    # was terminated before its shutdown handler could archive them. Archive
    # must succeed before clearing the table or accepting this session's data.
    try:
        previous_archive = archive_events()
    except (OSError, sqlite3.Error, csv.Error) as error:
        raise RuntimeError(
            "Could not archive the previous gateway session; refusing to "
            "clear its dashboard events."
        ) from error
    if previous_archive is not None:
        print(f"Previous gateway event archive saved: {previous_archive}")

    clear_event_history_all()
    print("SmartSeal+ gateway started.")
    print("Previous session archived; starting with an empty live dashboard.")
    last_stale_check = 0.0
    artifact_queue = queue.Queue(maxsize=64)
    artifact_thread = threading.Thread(
        target=_artifact_worker,
        args=(artifact_queue,),
        name="smartseal-image-worker",
        daemon=True,
    )
    artifact_thread.start()

    try:
        while True:
            try:
                scan_result = scanner()
                if scan_result is None:
                    print("No sensor packet received; retrying BLE scan.")
                    continue

                raw_packets = (
                    scan_result
                    if isinstance(scan_result, (list, tuple))
                    else [scan_result]
                )
                for raw_packet in raw_packets:
                    try:
                        packet = parse_packet(raw_packet)
                        if packet is None:
                            print("Invalid sensor packet. Skipping...")
                            continue

                        # Stamp each seal event with the most recent fresh fix
                        # from the gateway's GPS receiver, if one is available.
                        if gps_tracker is not None:
                            packet.update(gps_tracker.latest_fix() or {})

                        if not accept_event(packet):
                            print(
                                "Stale or duplicate packet ignored: "
                                f"seal={packet['seal_id']} "
                                f"seq={packet['event_sequence']}"
                            )
                            continue

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
                        alerts = process_alerts(packet)
                        temperature_out_of_range = (
                            packet["temperature"] is not None
                            and (
                                packet["temperature"] < TEMP_LOW
                                or packet["temperature"] > TEMP_HIGH
                            )
                        )
                        capture_triggered = (
                            packet["tamper"]
                            or packet["vibration"]
                            or packet["movement_type"] != 0
                        )

                        ai_analysis = (
                            "Temperature out of bounds; image capture skipped."
                            if temperature_out_of_range and not capture_triggered
                            else "No issues detected."
                        )
                        if capture_triggered:
                            try:
                                artifact_queue.put_nowait(packet)
                                ai_analysis = "Image analysis queued."
                            except queue.Full:
                                ai_analysis = (
                                    "Image analysis skipped; background queue is full."
                                )
                                print(
                                    "Image analysis queue full; skipping image work "
                                    f"for seal={packet['seal_id']} "
                                    f"seq={packet['event_sequence']}"
                                )
                            update_event_artifacts(packet, None, ai_analysis)
                        else:
                            update_event_artifacts(packet, None, ai_analysis)

                        print("\nPacket Received")
                        print(packet)
                        for alert in alerts:
                            print("ALERT:", alert)
                        print("Analysis:", ai_analysis)
                    except Exception as error:
                        print(f"Packet processing error: {error}")
                time.sleep(interval)
            except Exception as error:
                print(f"Gateway processing error: {error}")
                time.sleep(interval)
    except KeyboardInterrupt:
        print("\nSmartSeal+ gateway stopped.")
    finally:
        if gps_tracker is not None:
            gps_tracker.stop()
        # Drain queued image work before archiving so completed image paths and
        # analysis results are reflected in the archive.
        artifact_queue.put(None)
        artifact_queue.join()
        artifact_thread.join()
        try:
            archive_path = archive_events()
            if archive_path is not None:
                print(f"Gateway event archive saved: {archive_path}")
            else:
                print("No gateway events to archive.")
            # A successful archive lets the next run start with a clean live
            # dashboard without archiving the same session a second time.
            clear_event_history_all()
        except (OSError, sqlite3.Error, csv.Error) as error:
            print(f"ERROR: Could not archive gateway events: {error}")


if __name__ == "__main__":
    run_gateway()
