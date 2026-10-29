"""Tests for the SmartSeal+ secure packet validation pipeline."""

import os
import unittest
from unittest.mock import patch

from Gateway.message_auth import generate_hmac
from Gateway.secure_packet_validator import SecurePacketValidator


class TestSecurePacketValidator(unittest.TestCase):

    def setUp(self):
        self.key = bytes.fromhex("a1" * 32)
        self.validator = SecurePacketValidator()

        self.packet = {
            "seal_id": 1,
            "event_sequence": 100,
            "temperature": 72.5,
            "tamper": False,
            "vibration": 1.23,
        }

        self.environment = patch.dict(
            os.environ,
            {"SMARTSEAL_KEY_1": self.key.hex()},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def signed_packet(self, packet=None, key=None):
        data = (packet or self.packet).copy()
        secret = key if key is not None else self.key

        data["hmac"] = generate_hmac(data, secret)
        return data

    def test_valid_packet_accepted(self):
        accepted, reason = self.validator.validate_packet(
            self.signed_packet()
        )

        self.assertTrue(accepted)
        self.assertEqual(reason, "accepted")

    def test_invalid_hmac_rejected(self):
        packet = self.signed_packet()
        packet["hmac"] = "0" * 64

        accepted, reason = self.validator.validate_packet(packet)

        self.assertFalse(accepted)
        self.assertEqual(reason, "message authentication failed")

    def test_modified_temperature_rejected(self):
        packet = self.signed_packet()
        packet["temperature"] = 95.0

        accepted, _ = self.validator.validate_packet(packet)

        self.assertFalse(accepted)

    def test_duplicate_packet_rejected(self):
        packet = self.signed_packet()

        self.assertTrue(self.validator.validate_packet(packet)[0])

        accepted, reason = self.validator.validate_packet(packet)

        self.assertFalse(accepted)
        self.assertEqual(reason, "duplicate event")

    def test_outdated_sequence_rejected(self):
        self.validator.validate_packet(self.signed_packet())

        older = self.packet.copy()
        older["event_sequence"] = 99

        accepted, reason = self.validator.validate_packet(
            self.signed_packet(older)
        )

        self.assertFalse(accepted)
        self.assertEqual(reason, "outdated event sequence")

    def test_newer_sequence_accepted(self):
        self.validator.validate_packet(self.signed_packet())

        newer = self.packet.copy()
        newer["event_sequence"] = 101

        accepted, reason = self.validator.validate_packet(
            self.signed_packet(newer)
        )

        self.assertTrue(accepted)
        self.assertEqual(reason, "accepted")

    def test_missing_hmac_rejected(self):
        accepted, reason = self.validator.validate_packet(
            self.packet.copy()
        )

        self.assertFalse(accepted)
        self.assertEqual(reason, "message authentication failed")

    def test_missing_device_key_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            accepted, reason = self.validator.validate_packet(
                self.signed_packet()
            )

        self.assertFalse(accepted)
        self.assertEqual(
            reason,
            "device authentication key unavailable",
        )

    def test_invalid_seal_id_rejected(self):
        packet = self.packet.copy()
        packet["seal_id"] = 0

        accepted, reason = self.validator.validate_packet(packet)

        self.assertFalse(accepted)
        self.assertEqual(reason, "invalid seal ID")

    def test_invalid_packet_format_rejected(self):
        accepted, reason = self.validator.validate_packet("invalid")

        self.assertFalse(accepted)
        self.assertEqual(reason, "invalid packet format")

    def test_failed_authentication_does_not_advance_sequence(self):
        forged = self.packet.copy()
        forged["event_sequence"] = 999
        forged["hmac"] = "invalid"

        self.assertFalse(self.validator.validate_packet(forged)[0])

        valid = self.signed_packet()

        accepted, reason = self.validator.validate_packet(valid)

        self.assertTrue(accepted)
        self.assertEqual(reason, "accepted")

    def test_wrong_device_key_rejected(self):
        wrong_key = bytes.fromhex("b2" * 32)

        packet = self.signed_packet(key=wrong_key)

        accepted, reason = self.validator.validate_packet(packet)

        self.assertFalse(accepted)
        self.assertEqual(reason, "message authentication failed")


if __name__ == "__main__":
    unittest.main()