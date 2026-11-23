"""SmartSeal+ gateway with validation, idempotent storage, and delivery ACKs."""

import csv
import os
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
        recover_artifact_jobs,
        claim_artifact_job,
        save_artifact_image,
        retry_artifact_job,
        complete_artifact_job,
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
        recover_artifact_jobs,
        claim_artifact_job,
        save_artifact_image,
        retry_artifact_job,
        complete_artifact_job,
    )
    from alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
    from ai_analyzer import analyze_image
    from camera_manager import capture_image
    from image_storage import image_path
    from gps_tracker import GPSLocationTracker


def _artifact_worker(stop_event):
    """Process durable image jobs without blocking BLE scanning."""
    while True:
        if stop_event.is_set():
            return
        job = None
        try:
            job = claim_artifact_job()
            if job is None:
                stop_event.wait(1)
                continue

            job_id, packet, image_filename = job
            if not image_filename or not image_path(image_filename).is_file():
                image_filename = capture_image(packet)
                save_artifact_image(job_id, image_filename)

            if image_filename and image_path(image_filename).is_file():
                ai_analysis = analyze_image(str(image_path(image_filename)), packet)
            else:
                ai_analysis = "Alert detected; image unavailable."

            complete_artifact_job(job_id, packet, image_filename, ai_analysis)
            print(
                f"Background image analysis complete: seal={packet['seal_id']} "
                f"seq={packet['event_sequence']} — {ai_analysis}"
            )
        except Exception as error:
            print(f"Background image processing error: {error}")
            if job is not None:
                try:
                    retry_artifact_job(job[0])
                except Exception as retry_error:
                    print(f"Could not preserve image-analysis job: {retry_error}")
            stop_event.wait(5)


def run_gateway(interval=5, scanner=scan_ble):
    simulation_mode = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"
    init_database()
    recover_artifact_jobs()
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
    artifact_stop = threading.Event()
    artifact_thread = threading.Thread(
        target=_artifact_worker,
        args=(artifact_stop,),
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
                    # A real scanner has already spent its scan window waiting.
                    # Keep a brief backoff for adapter errors, but don't add the
                    # simulation interval after every empty BLE scan.
                    time.sleep(interval if simulation_mode else 0.25)
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

                        capture_triggered = (
                            packet["tamper"]
                            or packet["vibration"]
                            or packet["movement_type"] != 0
                        )
                        if not accept_event(packet, artifact_required=capture_triggered):
                            print(
                                "Stale or duplicate packet ignored: "
                                f"seal={packet['seal_id']} "
                                f"seq={packet['event_sequence']}"
                            )
                            continue
                        # The database may accept the event but skip the image
                        # job when its bounded persistent queue is full.
                        artifact_queued = packet.pop(
                            "_artifact_queued", capture_triggered
                        )

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
                        ai_analysis = (
                            "Temperature out of bounds; image capture skipped."
                            if temperature_out_of_range and not capture_triggered
                            else "No issues detected."
                        )
                        if capture_triggered:
                            ai_analysis = (
                                "Image analysis queued."
                                if artifact_queued
                                else "Image analysis skipped; persistent queue is full."
                            )
                            if not artifact_queued:
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
                # The real BLE scanner blocks for SCAN_TIMEOUT. Sleeping again
                # here left a five-second blind period after each five-second
                # scan and caused the gateway to miss seal sequence updates.
                # Simulation scanners return immediately, so preserve their
                # configured pacing to avoid generating synthetic events in a
                # tight loop.
                if simulation_mode:
                    time.sleep(interval)
            except Exception as error:
                print(f"Gateway processing error: {error}")
                time.sleep(interval if simulation_mode else 0.5)
    except KeyboardInterrupt:
        print("\nSmartSeal+ gateway stopped.")
    finally:
        if gps_tracker is not None:
            gps_tracker.stop()
        # Let an in-progress job finish. Unprocessed durable jobs will resume
        # the next time the gateway starts.
        artifact_stop.set()
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
