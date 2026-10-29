"""Automated tests for SmartSeal+ HMAC authentication."""

import unittest

from Gateway.message_auth import generate_hmac, verify_hmac


class TestMessageAuthentication(unittest.TestCase):

    def setUp(self):
        self.secret_key = b"smartseal-test-key-not-for-production"

        self.packet = {
            "seal_id": 1,
            "event_sequence": 100,
            "temperature": 72.5,
            "tamper": False,
            "vibration": 1.23,
        }

    def test_generate_hmac(self):
        tag = generate_hmac(self.packet, self.secret_key)

        self.assertEqual(len(tag), 64)
        self.assertIsInstance(tag, str)

    def test_valid_hmac_accepted(self):
        tag = generate_hmac(self.packet, self.secret_key)

        self.assertTrue(
            verify_hmac(self.packet, self.secret_key, tag)
        )

    def test_invalid_hmac_rejected(self):
        self.assertFalse(
            verify_hmac(self.packet, self.secret_key, "invalid")
        )

    def test_modified_temperature_rejected(self):
        tag = generate_hmac(self.packet, self.secret_key)

        modified = self.packet.copy()
        modified["temperature"] = 95.0

        self.assertFalse(
            verify_hmac(modified, self.secret_key, tag)
        )

    def test_modified_sequence_rejected(self):
        tag = generate_hmac(self.packet, self.secret_key)

        modified = self.packet.copy()
        modified["event_sequence"] = 101

        self.assertFalse(
            verify_hmac(modified, self.secret_key, tag)
        )

    def test_modified_vibration_rejected(self):
        tag = generate_hmac(self.packet, self.secret_key)

        modified = self.packet.copy()
        modified["vibration"] = 2.5

        self.assertFalse(
            verify_hmac(modified, self.secret_key, tag)
        )

    def test_missing_hmac_rejected(self):
        self.assertFalse(
            verify_hmac(self.packet, self.secret_key, None)
        )

    def test_malformed_hmac_rejected(self):
        self.assertFalse(
            verify_hmac(self.packet, self.secret_key, 12345)
        )

    def test_field_order_does_not_change_hmac(self):
        reordered = dict(reversed(list(self.packet.items())))

        self.assertEqual(
            generate_hmac(self.packet, self.secret_key),
            generate_hmac(reordered, self.secret_key),
        )

    def test_missing_required_field_rejected(self):
        tag = generate_hmac(self.packet, self.secret_key)

        incomplete = self.packet.copy()
        del incomplete["temperature"]

        self.assertFalse(
            verify_hmac(incomplete, self.secret_key, tag)
        )


if __name__ == "__main__":
    unittest.main()