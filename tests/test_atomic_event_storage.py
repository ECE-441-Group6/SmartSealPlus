
"""Tests for atomic event storage and replay protection."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from Gateway import database
from Gateway.replay_protection import ReplayProtector


class TestAtomicEventStorage(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

        self.db_path = (
            Path(self.temp_directory.name) / "atomic_test.db"
        )

        db_patch = patch.object(
            database, "DB_NAME", self.db_path
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)

        database.init_database()

        # Initialize the persistent replay-protection table.
        ReplayProtector(db_path=self.db_path)

    def packet(self, sequence):
        return {
            "seal_id": 1,
            "event_sequence": sequence,
            "temperature": 72.5,
            "tamper": False,
            "vibration": 1.23,
        }

    def last_sequence(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT last_sequence
                FROM security_sequences
                WHERE seal_id = 1
                """
            ).fetchone()

        return None if row is None else row[0]

    def event_count(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM events"
            ).fetchone()[0]

        return count

    def test_valid_event_stored(self):
        result = database.accept_and_store_event(
            self.packet(100)
        )

        self.assertEqual(result, (True, "accepted"))
        self.assertEqual(self.event_count(), 1)
        self.assertEqual(self.last_sequence(), 100)

    def test_duplicate_event_rejected(self):
        database.accept_and_store_event(self.packet(100))

        result = database.accept_and_store_event(
            self.packet(100)
        )

        self.assertEqual(
            result,
            (False, "duplicate event"),
        )
        self.assertEqual(self.event_count(), 1)
        self.assertEqual(self.last_sequence(), 100)

    def test_outdated_event_rejected(self):
        database.accept_and_store_event(self.packet(100))

        result = database.accept_and_store_event(
            self.packet(99)
        )

        self.assertEqual(
            result,
            (False, "outdated event sequence"),
        )
        self.assertEqual(self.event_count(), 1)
        self.assertEqual(self.last_sequence(), 100)

    def test_newer_event_accepted(self):
        database.accept_and_store_event(self.packet(100))

        result = database.accept_and_store_event(
            self.packet(101)
        )

        self.assertEqual(result, (True, "accepted"))
        self.assertEqual(self.event_count(), 2)
        self.assertEqual(self.last_sequence(), 101)

    def test_failed_insertion_does_not_advance_sequence(self):
        database.accept_and_store_event(self.packet(100))

        # Simulate a database insertion failure.
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute("""
                    CREATE TRIGGER block_sequence_101
                    BEFORE INSERT ON events
                    WHEN NEW.event_sequence = 101
                    BEGIN
                        SELECT RAISE(
                            ABORT,
                            'simulated storage failure'
                        );
                    END;
                """)

        result = database.accept_and_store_event(
            self.packet(101)
        )

        self.assertEqual(
            result,
            (False, "database transaction failed"),
        )
        self.assertEqual(self.event_count(), 1)
        self.assertEqual(self.last_sequence(), 100)

        # Remove the simulated failure.
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute(
                    "DROP TRIGGER block_sequence_101"
                )

        # Retry the same event after recovery.
        retry = database.accept_and_store_event(
            self.packet(101)
        )

        self.assertEqual(retry, (True, "accepted"))
        self.assertEqual(self.event_count(), 2)
        self.assertEqual(self.last_sequence(), 101)


if __name__ == "__main__":
    unittest.main()
