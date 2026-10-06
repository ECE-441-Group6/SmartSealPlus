# Main Raspberry Pi program. Starts BLE scanning, receives SmartSeal data, processes events, updates storage, and communicates with the dashboard.
from ble_scanner import scan_ble
from packet_parser import parse_packet
from database import init_database, insert_event
from alert_manager import process_alerts

import time

init_database()

while True:

    raw_packet = scan_ble()

    packet = parse_packet(raw_packet)

    if packet:

        insert_event(packet)

        alerts = process_alerts(packet)

        print("\nPacket Received")
        print(packet)

        for alert in alerts:
            print("ALERT:", alert)

    time.sleep(5)