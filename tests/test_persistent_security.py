"""Integration tests for persistent SmartSeal+ packet security."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Gateway.message_auth import generate_hmac
from Gateway.secure_packet_validator import SecurePacketValidator


class TestPersistentSecurity(unittest.TestCase):

    def setUp(self):
        self.key = bytes.fromhex("a1" * 32)

        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

        self.db_path = (
            Path(self.temp_directory.name) / "security_test.db"
        )

        self.environment = patch.dict(
            os.environ,
            {"SMARTSEAL_KEY_1": self.key.hex()},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def signed_packet(self, sequence):
        packet = {
            "seal_id": 1,
            "event_sequence": sequence,
            "temperature": 72.5,
            "tamper": False,
            "vibration": 1.23,
        }

        packet["hmac"] = generate_hmac(packet, self.key)
        return packet

    def test_valid_authenticated_packet(self):
        validator = SecurePacketValidator(db_path=self.db_path)

        self.assertEqual(
            validator.validate_packet(self.signed_packet(100)),
            (True, "accepted"),
        )

    def test_duplicate_rejected_after_restart(self):
        first = SecurePacketValidator(db_path=self.db_path)
        self.assertTrue(
            first.validate_packet(self.signed_packet(100))[0]
        )

        restarted = SecurePacketValidator(db_path=self.db_path)

        self.assertEqual(
            restarted.validate_packet(self.signed_packet(100)),
            (False, "duplicate event"),
        )

    def test_outdated_packet_rejected(self):
        validator = SecurePacketValidator(db_path=self.db_path)

        validator.validate_packet(self.signed_packet(100))

        self.assertEqual(
            validator.validate_packet(self.signed_packet(99)),
            (False, "outdated event sequence"),
        )

    def test_modified_packet_rejected(self):
        validator = SecurePacketValidator(db_path=self.db_path)

        packet = self.signed_packet(100)
        packet["temperature"] = 95.0

        self.assertEqual(
            validator.validate_packet(packet),
            (False, "message authentication failed"),
        )

    def test_newer_packet_accepted(self):
        validator = SecurePacketValidator(db_path=self.db_path)

        validator.validate_packet(self.signed_packet(100))

        self.assertEqual(
            validator.validate_packet(self.signed_packet(101)),
            (True, "accepted"),
        )

    def test_replay_rejected_after_second_restart(self):
        first = SecurePacketValidator(db_path=self.db_path)
        first.validate_packet(self.signed_packet(100))

        second = SecurePacketValidator(db_path=self.db_path)
        second.validate_packet(self.signed_packet(101))

        third = SecurePacketValidator(db_path=self.db_path)

        self.assertEqual(
            third.validate_packet(self.signed_packet(101)),
            (False, "duplicate event"),
        )

    def test_failed_authentication_does_not_advance_database(self):
        validator = SecurePacketValidator(db_path=self.db_path)

        self.assertEqual(
            validator.validate_packet(self.signed_packet(100)),
            (True, "accepted"),
        )

        forged = self.signed_packet(999)
        forged["temperature"] = 95.0

        self.assertEqual(
            validator.validate_packet(forged),
            (False, "message authentication failed"),
        )

        restarted = SecurePacketValidator(db_path=self.db_path)

        self.assertEqual(
            restarted.validate_packet(self.signed_packet(101)),
            (True, "accepted"),
        )


if __name__ == "__main__":
    unittest.main()
