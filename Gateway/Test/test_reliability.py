import tempfile
import unittest
from pathlib import Path

from Gateway import database
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

if __name__ == "__main__":
    unittest.main()
