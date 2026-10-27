import unittest

from Gateway.alert_manager import process_alerts


class TestAlertManager(unittest.TestCase):

    def make_packet(self, temperature=5.0, tamper=False, vibration=False):
        return {
            "seal_id": 1,
            "temperature": temperature,
            "tamper": tamper,
            "vibration": vibration
        }

    def test_normal_temperature(self):
        packet = self.make_packet(temperature=5.0)
        self.assertEqual(process_alerts(packet), [])

    def test_high_temperature(self):
        packet = self.make_packet(temperature=9.5)
        self.assertIn("HIGH TEMPERATURE", process_alerts(packet))

    def test_low_temperature(self):
        packet = self.make_packet(temperature=1.0)
        self.assertIn("LOW TEMPERATURE", process_alerts(packet))

    def test_tamper_detection(self):
        packet = self.make_packet(tamper=True)
        self.assertIn("TAMPER DETECTED", process_alerts(packet))

    def test_vibration_detection(self):
        packet = self.make_packet(vibration=True)
        self.assertIn("VIBRATION EVENT", process_alerts(packet))

    def test_multiple_alerts(self):
        packet = self.make_packet(
            temperature=9.5,
            tamper=True,
            vibration=True
        )

        alerts = process_alerts(packet)

        self.assertEqual(len(alerts), 3)
        self.assertIn("HIGH TEMPERATURE", alerts)
        self.assertIn("TAMPER DETECTED", alerts)
        self.assertIn("VIBRATION EVENT", alerts)

    def test_lower_temperature_boundary(self):
        packet = self.make_packet(temperature=2.0)
        self.assertEqual(process_alerts(packet), [])

    def test_upper_temperature_boundary(self):
        packet = self.make_packet(temperature=8.0)
        self.assertEqual(process_alerts(packet), [])


if __name__ == "__main__":
    unittest.main()