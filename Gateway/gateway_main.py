# Main Raspberry Pi program. Starts BLE scanning, receives SmartSeal data, processes events, and stores readings for the dashboard.
from ble_scanner import scan_ble
from packet_parser import parse_packet
from database import init_database, insert_event
from alert_manager import process_alerts
from ai_analyzer import analyze_image
from camera_manager import capture_image
from image_storage import image_path

import time


def run_gateway(interval=5):
    # Prepare storage before continuously processing incoming advertisements.
    init_database()

    while True:
        # Receive a raw advertisement and normalize it into the gateway packet
        # shape used by alerts, storage, image capture, and AI analysis.
        raw_packet = scan_ble()
        packet = parse_packet(raw_packet)

        if packet:
            # Evaluate all sensor thresholds for this packet.
            alerts = process_alerts(packet)
            image_filename = None
            ai_analysis = None

            if packet["tamper"] or packet["vibration"]:
                # Capture evidence only for physical events that need review.
                image_filename = capture_image(packet)
                ai_analysis = analyze_image(
                    str(image_path(image_filename)),
                    packet,
                )

            # Persist every valid reading, including readings without alerts.
            insert_event(packet, image_filename, ai_analysis)

            print("\nPacket Received")
            print(packet)

            for alert in alerts:
                print("ALERT:", alert)

            if ai_analysis:
                print("AI:", ai_analysis)

        time.sleep(interval)


if __name__ == "__main__":
    run_gateway()