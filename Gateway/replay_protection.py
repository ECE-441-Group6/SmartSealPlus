"""Sequence validation utilities for SmartSeal+ sensor events."""

MAX_SEQUENCE = 0xFFFFFFFF


class ReplayProtector:
    """Track event sequences independently for each seal."""

    def __init__(self):
        self.last_sequences = {}

    def check_sequence(self, seal_id, sequence):
        """
        Check whether an event sequence is newer than the last
        accepted sequence for this seal.

        Returns:
            (True, "accepted") for a new sequence.
            (False, reason) for an invalid or outdated sequence.
        """

        if (
            not isinstance(seal_id, int)
            or isinstance(seal_id, bool)
            or seal_id < 1
        ):
            return False, "invalid seal ID"

        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or not 0 <= sequence <= MAX_SEQUENCE
        ):
            return False, "invalid event sequence"

        previous = self.last_sequences.get(seal_id)

        if previous is not None:
            if sequence == previous:
                return False, "duplicate event"

            if sequence < previous:
                return False, "outdated event sequence"

        self.last_sequences[seal_id] = sequence

        return True, "accepted"