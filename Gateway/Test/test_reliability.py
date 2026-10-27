import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from Gateway import database
from Gateway import gateway_main
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

    def packet(self, seal_id=1, sequence=1, temperature=5.0, tamper=False):
        return parse_packet(parse_advertisement(
            f"S:{seal_id},E:{sequence},T:{temperature},A:{int(tamper)},V:0"
        ))

    def test_normal_and_critical_packets_are_parsed(self):
        normal = self.packet()
        critical = self.packet(sequence=2, temperature=9.0, tamper=True)
        self.assertFalse(normal["tamper"])
        self.assertEqual(critical["event_sequence"], 2)
        self.assertFalse(critical["tamper"])
        self.assertGreater(critical["temperature"], 8)

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
            "gateway-events-*.csv"
        ))
        self.assertEqual(len(archives), 1)
        with archives[0].open(newline="", encoding="utf-8") as archive_file:
            rows = list(csv.DictReader(archive_file))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_sequence"], "7")

if __name__ == "__main__":
    unittest.main()
