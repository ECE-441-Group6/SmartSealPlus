"""Unit tests for SmartSeal+ replay sequence validation."""

import unittest

from Gateway.replay_protection import ReplayProtector


class TestReplayProtection(unittest.TestCase):

    def setUp(self):
        self.protector = ReplayProtector()

    def test_first_event_accepted(self):
        accepted, reason = self.protector.check_sequence(1, 100)

        self.assertTrue(accepted)
        self.assertEqual(reason, "accepted")

    def test_increasing_sequence_accepted(self):
        self.protector.check_sequence(1, 100)

        accepted, reason = self.protector.check_sequence(1, 101)

        self.assertTrue(accepted)
        self.assertEqual(reason, "accepted")

    def test_duplicate_sequence_rejected(self):
        self.protector.check_sequence(1, 100)

        accepted, reason = self.protector.check_sequence(1, 100)

        self.assertFalse(accepted)
        self.assertEqual(reason, "duplicate event")

    def test_outdated_sequence_rejected(self):
        self.protector.check_sequence(1, 100)

        accepted, reason = self.protector.check_sequence(1, 99)

        self.assertFalse(accepted)
        self.assertEqual(reason, "outdated event sequence")

    def test_different_seals_tracked_independently(self):
        self.protector.check_sequence(1, 100)

        accepted, reason = self.protector.check_sequence(2, 50)

        self.assertTrue(accepted)
        self.assertEqual(reason, "accepted")

    def test_invalid_seal_id_rejected(self):
        accepted, reason = self.protector.check_sequence(0, 100)

        self.assertFalse(accepted)
        self.assertEqual(reason, "invalid seal ID")

    def test_negative_sequence_rejected(self):
        accepted, reason = self.protector.check_sequence(1, -1)

        self.assertFalse(accepted)
        self.assertEqual(reason, "invalid event sequence")

    def test_sequence_above_32_bit_limit_rejected(self):
        accepted, reason = self.protector.check_sequence(
            1, 0x100000000
        )

        self.assertFalse(accepted)
        self.assertEqual(reason, "invalid event sequence")

    def test_boolean_sequence_rejected(self):
        accepted, reason = self.protector.check_sequence(1, True)

        self.assertFalse(accepted)
        self.assertEqual(reason, "invalid event sequence")

    def test_rejected_event_does_not_change_last_sequence(self):
        self.protector.check_sequence(1, 100)
        self.protector.check_sequence(1, 50)

        self.assertEqual(self.protector.last_sequences[1], 100)


if __name__ == "__main__":
    unittest.main()