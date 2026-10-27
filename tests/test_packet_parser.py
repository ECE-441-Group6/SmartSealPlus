import unittest
from Gateway.packet_parser import parse_packet


class TestPacketParser(unittest.TestCase):

    def test_valid_packet(self):
        packet = {
            "seal_id": 1,
            "temperature": 5.2,
            "tamper": False,
            "vibration": False
        }
        self.assertEqual(parse_packet(packet), packet)

    def test_missing_temperature(self):
        packet = {
            "seal_id": 1,
            "tamper": False,
            "vibration": False
        }
        self.assertIsNone(parse_packet(packet))

    def test_invalid_temperature(self):
        packet = {
            "seal_id": 1,
            "temperature": "HOT",
            "tamper": False,
            "vibration": False
        }
        self.assertIsNone(parse_packet(packet))

    def test_invalid_seal_id(self):
        packet = {
            "seal_id": -1,
            "temperature": 5.2,
            "tamper": False,
            "vibration": False
        }
        self.assertIsNone(parse_packet(packet))

    def test_invalid_tamper_status(self):
        packet = {
            "seal_id": 1,
            "temperature": 5.2,
            "tamper": "YES",
            "vibration": False
        }
        self.assertIsNone(parse_packet(packet))

    def test_invalid_vibration_status(self):
        packet = {
            "seal_id": 1,
            "temperature": 5.2,
            "tamper": False,
            "vibration": 1
        }
        self.assertIsNone(parse_packet(packet))


if __name__ == "__main__":
    unittest.main()