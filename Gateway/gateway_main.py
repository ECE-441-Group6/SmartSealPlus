"""SmartSeal+ gateway with error handling and continuous monitoring."""

import time

from ble_scanner import scan_ble
from packet_parser import parse_packet
from database import init_database, insert_event
from alert_manager import TEMP_HIGH, TEMP_LOW, process_alerts
from ai_analyzer import analyze_image
from camera_manager import capture_image
from image_storage import image_path


def run_gateway(interval=5):
    # Initialize the database before starting monitoring.
    init_database()
    print("SmartSeal+ gateway started.")

<<<<<<< HEAD
    while True:
        # Receive a raw advertisement and normalize it into the gateway packet
        # shape used by alerts, storage, image capture, and AI analysis.
        raw_packet = scan_ble()
        if raw_packet is None:
            print("No sensor packet received; retrying BLE scan.")
            # scan_ble already waits for the complete BLE scan window. Start the
            # next scan immediately after processing a valid reading.
            continue

        packet = parse_packet(raw_packet)
=======
    try:
        while True:
            try:
                # Receive and validate sensor data.
                raw_packet = scan_ble()
>>>>>>> 67fda2a (Improve gateway error handling and monitoring reliability)

                if raw_packet is None:
                    print("No BLE packet received. Retrying...")
                    continue

<<<<<<< HEAD
            temperature_out_of_range = (
                packet["temperature"] < TEMP_LOW
                or packet["temperature"] > TEMP_HIGH
            )

            if packet["tamper"] or packet["vibration"] or temperature_out_of_range:
                # Capture camera evidence for tamper, vibration, or temperature alerts.
                image_filename = capture_image(packet)
                ai_analysis = analyze_image(
                    str(image_path(image_filename)),
                    packet,
=======
                packet = parse_packet(raw_packet)

                if packet is None:
                    print("Invalid sensor packet. Skipping...")
                    continue

                # Evaluate sensor alerts.
                alerts = process_alerts(packet)

                temperature_out_of_range = (
                    packet["temperature"] < TEMP_LOW
                    or packet["temperature"] > TEMP_HIGH
>>>>>>> 67fda2a (Improve gateway error handling and monitoring reliability)
                )
            else:
                ai_analysis = "No issues detected."

                alert_triggered = (
                    packet["tamper"]
                    or packet["vibration"]
                    or temperature_out_of_range
                )

                image_filename = None
                ai_analysis = "No issues detected."

                if alert_triggered:
                    # Camera failure should not prevent event storage.
                    try:
                        image_filename = capture_image(packet)
                    except Exception as error:
                        print(f"Camera error: {error}")

                    # AI failure should not prevent event storage.
                    if image_filename:
                        try:
                            ai_analysis = analyze_image(
                                str(image_path(image_filename)),
                                packet
                            )
                        except Exception as error:
                            print(f"AI analysis error: {error}")
                            ai_analysis = "Analysis unavailable."
                    else:
                        ai_analysis = "Alert detected; image unavailable."

                # Save sensor data.
                try:
                    insert_event(packet, image_filename, ai_analysis)
                except Exception as error:
                    print(f"Database error: {error}")

                print("\nPacket Received")
                print(packet)

                for alert in alerts:
                    print("ALERT:", alert)

                print("Analysis:", ai_analysis)

            except Exception as error:
                print(f"Gateway processing error: {error}")

            finally:
                # Maintain a consistent polling interval.
                time.sleep(interval)

    except KeyboardInterrupt:
        print("\nSmartSeal+ gateway stopped safely.")


if __name__ == "__main__":
    run_gateway()