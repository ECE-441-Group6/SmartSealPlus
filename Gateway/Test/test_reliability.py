import csv
import io
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from Gateway import database
from Gateway import gateway_main
from Gateway.alert_manager import process_alerts
from Gateway.ble_scanner import parse_advertisement
from Gateway.packet_parser import parse_packet


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_name = database.DB_NAME
        database.DB_NAME = Path(self.temp_dir.name) / "smartseal.db"
        database.init_database()
    def tearDown(self):
        database.DB_NAME = self.old_db_name
        self.temp_dir.cleanup()

    def packet(
        self,
        seal_id=1,
        sequence=1,
        temperature=5.0,
        tamper=False,
        vibration=0.0,
    ):
        temperature_tenths = (
            int(temperature * 10)
        )
        payload = (
            bytes([0xA5, 1, seal_id])
            + sequence.to_bytes(4, "little")
            + temperature_tenths.to_bytes(2, "little", signed=True)
            + bytes([int(tamper)])
            + int(vibration * 100).to_bytes(2, "little")
        )
        return parse_packet(parse_advertisement(payload))

    def test_normal_and_critical_packets_are_parsed(self):
        normal = self.packet()
        critical = self.packet(sequence=2, temperature=9.0, tamper=True)
        self.assertFalse(normal["tamper"])
        self.assertEqual(critical["event_sequence"], 2)
        self.assertTrue(critical["tamper"])
        self.assertGreater(critical["temperature"], 8)

    def test_vibration_value_triggers_event(self):
        normal = self.packet(sequence=7)
        vibration = self.packet(sequence=8, vibration=1.0)

        self.assertEqual(normal["vibration"], 0.0)
        self.assertEqual(vibration["vibration"], 1.0)
        self.assertNotIn("VIBRATION EVENT", process_alerts(normal))
        self.assertIn("VIBRATION EVENT", process_alerts(vibration))

    def test_retransmission_is_idempotent_and_seals_are_independent(self):
        first = self.packet(sequence=7)
        other_seal = self.packet(seal_id=2, sequence=7)
        self.assertTrue(database.insert_event(first))
        self.assertFalse(database.insert_event(first))
        self.assertTrue(database.insert_event(other_seal))
        self.assertEqual(len(database.get_latest_events()), 2)

    def test_clear_event_history_clears_events_and_seal_status(self):
        packet = self.packet(sequence=7)
        database.insert_event(packet)
        database.record_seen(packet)

        database.clear_event_history()

        self.assertEqual(database.get_latest_events(), [])
        self.assertEqual(database.get_stale_seals(0), [])

    def test_archive_events_exports_all_event_fields(self):
        first = self.packet(sequence=7, temperature=5.5)
        second = self.packet(sequence=8, temperature=6.5)
        database.insert_event(first, ai_analysis="first event")
        database.insert_event(second, ai_analysis="second event")

        archive_path = database.archive_events()

        with archive_path.open(newline="", encoding="utf-8") as archive_file:
            rows = list(csv.DictReader(archive_file))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["event_sequence"], "7")
        self.assertEqual(rows[1]["event_sequence"], "8")
        self.assertEqual(rows[1]["ai_analysis"], "second event")

    def test_gateway_shutdown_archives_events(self):
        packet = self.packet(sequence=7)
        calls = 0

        def stop_gateway():
            nonlocal calls
            calls += 1
            if calls == 1:
                return packet
            raise KeyboardInterrupt

        with redirect_stdout(io.StringIO()):
            gateway_main.run_gateway(interval=0, scanner=stop_gateway)

        archives = list((Path(database.DB_NAME).parent / "archives").glob(
            "SmartSeal_Events_*.csv"
        ))
        self.assertEqual(len(archives), 1)
        with archives[0].open(newline="", encoding="utf-8") as archive_file:
            rows = list(csv.DictReader(archive_file))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_sequence"], "7")

    def test_gateway_scans_while_image_capture_runs_in_background(self):
        packet = {
            "seal_id": 1,
            "event_sequence": 7,
            "temperature": 5.0,
            "tamper": True,
            "vibration": 0.0,
            "movement_type": 0,
        }
        capture_started = threading.Event()
        release_capture = threading.Event()
        calls = 0
        capture_started_during_scan = False

        def capture_image(_packet):
            capture_started.set()
            if not release_capture.wait(timeout=2):
                raise TimeoutError("Test did not release background capture")
            return "capture.jpg"

        def scan():
            nonlocal calls, capture_started_during_scan
            calls += 1
            if calls == 1:
                return packet
            capture_started_during_scan = capture_started.wait(timeout=2)
            release_capture.set()
            raise KeyboardInterrupt

        with (
            patch.object(gateway_main, "capture_image", side_effect=capture_image),
            patch.object(
                gateway_main, "analyze_image", return_value="test analysis"
            ),
            redirect_stdout(io.StringIO()),
        ):
            gateway_main.run_gateway(interval=0, scanner=scan)

        self.assertEqual(calls, 2)
        self.assertTrue(capture_started_during_scan)
        event = database.get_latest_events()[0]
        self.assertEqual(event[8], "capture.jpg")
        self.assertEqual(event[9], "test analysis")

if __name__ == "__main__":
    unittest.main()
