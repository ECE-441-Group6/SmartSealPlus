import unittest
from Gateway.packet_parser import parse_packet


class TestPacketParser(unittest.TestCase):

    def make_packet(self, **changes):
        packet = {
            "seal_id": 1,
            "event_sequence": 1,
            "temperature": 5.2,
            "vibration": 0.5
        }
        packet.update(changes)
        return packet

    def test_valid_packet(self):
        packet = self.make_packet()

        expected = {
            "seal_id": 1,
            "event_sequence": 1,
            "temperature": 5.2,
            "tamper": False,
            "vibration": 0.5
        }

        self.assertEqual(parse_packet(packet), expected)

    def test_missing_temperature(self):
        packet = self.make_packet()
        del packet["temperature"]

        self.assertIsNone(parse_packet(packet))

    def test_invalid_temperature(self):
        packet = self.make_packet(temperature="HOT")

        self.assertIsNone(parse_packet(packet))

    def test_invalid_seal_id(self):
        packet = self.make_packet(seal_id=-1)

        self.assertIsNone(parse_packet(packet))

    def test_missing_event_sequence(self):
        packet = self.make_packet()
        del packet["event_sequence"]

        self.assertIsNone(parse_packet(packet))

    def test_invalid_event_sequence(self):
        packet = self.make_packet(event_sequence=-1)

        self.assertIsNone(parse_packet(packet))

    def test_event_sequence_too_large(self):
        packet = self.make_packet(event_sequence=0x100000000)

        self.assertIsNone(parse_packet(packet))

    def test_event_sequence_boundaries(self):
        for sequence in (0, 0xFFFFFFFF):
            with self.subTest(sequence=sequence):
                packet = self.make_packet(event_sequence=sequence)
                result = parse_packet(packet)

                self.assertIsNotNone(result)
                self.assertEqual(result["event_sequence"], sequence)

    def test_invalid_vibration(self):
        packet = self.make_packet(vibration=-0.5)

        self.assertIsNone(parse_packet(packet))

    def test_vibration_boolean_rejected(self):
        packet = self.make_packet(vibration=True)

        self.assertIsNone(parse_packet(packet))

    def test_zero_vibration(self):
        packet = self.make_packet(vibration=0.0)

        result = parse_packet(packet)

        self.assertIsNotNone(result)
        self.assertEqual(result["vibration"], 0.0)

    def test_nonfinite_temperature(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                packet = self.make_packet(temperature=value)
                self.assertIsNone(parse_packet(packet))

    def test_nonfinite_vibration(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                packet = self.make_packet(vibration=value)
                self.assertIsNone(parse_packet(packet))

    def test_boolean_temperature_rejected(self):
        packet = self.make_packet(temperature=True)

        self.assertIsNone(parse_packet(packet))

    def test_boolean_seal_id_rejected(self):
        packet = self.make_packet(seal_id=True)

        self.assertIsNone(parse_packet(packet))

    def test_tamper_defaults_to_false(self):
        packet = self.make_packet()

        result = parse_packet(packet)

        self.assertIsNotNone(result)
        self.assertFalse(result["tamper"])

    def test_none_packet(self):
        self.assertIsNone(parse_packet(None))


if __name__ == "__main__":
    unittest.main()