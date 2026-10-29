import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Gateway import database


class TestDatabase(unittest.TestCase):

    def setUp(self):
        # Create a separate temporary database for each test.
        self.temp_dir = tempfile.TemporaryDirectory()

        # Register cleanup in the correct order:
        # stop patching first, then delete temporary files.
        self.addCleanup(self.temp_dir.cleanup)

        self.test_db = Path(self.temp_dir.name) / "test_smartseal.db"

        db_patch = patch.object(database, "DB_NAME", self.test_db)
        db_patch.start()
        self.addCleanup(db_patch.stop)

        database.init_database()

    def make_packet(self, sequence=1, **changes):
        packet = {
            "seal_id": 1,
            "event_sequence": sequence,
            "temperature": 5.5,
            "tamper": False,
            "vibration": 0.5
        }
        packet.update(changes)
        return packet

    def test_database_creation(self):
        self.assertTrue(self.test_db.exists())

    def test_events_table_exists(self):
        conn = sqlite3.connect(self.test_db)

        try:
            result = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='events'"
            ).fetchone()

            self.assertIsNotNone(result)

        finally:
            conn.close()

    def test_insert_event(self):
        inserted = database.insert_event(self.make_packet())

        events = database.get_latest_events()

        self.assertTrue(inserted)
        self.assertEqual(len(events), 1)

    def test_sensor_values(self):
        database.insert_event(self.make_packet())

        event = database.get_latest_events()[0]

        self.assertEqual(event[2], 1)       # seal_id
        self.assertEqual(event[3], 1)       # event_sequence
        self.assertEqual(event[4], 5.5)     # temperature
        self.assertEqual(event[5], 0)       # tamper
        self.assertEqual(event[6], 0.5)     # vibration

    def test_image_and_ai_analysis(self):
        database.insert_event(
            self.make_packet(),
            image_filename="test_image.jpg",
            ai_analysis="No visible damage"
        )

        event = database.get_latest_events()[0]

        self.assertEqual(event[7], "test_image.jpg")
        self.assertEqual(event[8], "No visible damage")

    def test_multiple_events(self):
        for i in range(5):
            packet = self.make_packet(
                sequence=i + 1,
                temperature=3.0 + i
            )
            database.insert_event(packet)

        events = database.get_latest_events()

        self.assertEqual(len(events), 5)

    def test_empty_database(self):
        events = database.get_latest_events()

        self.assertEqual(events, [])

    def test_database_initialization_twice(self):
        database.init_database()
        database.init_database()

        self.assertTrue(self.test_db.exists())

    def test_duplicate_event_prevention(self):
        packet = self.make_packet(sequence=10)

        first_insert = database.insert_event(packet)
        second_insert = database.insert_event(packet)

        events = database.get_latest_events()

        self.assertTrue(first_insert)
        self.assertFalse(second_insert)
        self.assertEqual(len(events), 1)

    def test_same_sequence_different_seals(self):
        packet1 = self.make_packet(sequence=1, seal_id=1)
        packet2 = self.make_packet(sequence=1, seal_id=2)

        database.insert_event(packet1)
        database.insert_event(packet2)

        events = database.get_latest_events()

        self.assertEqual(len(events), 2)

    def test_update_event_artifacts(self):
        packet = self.make_packet(sequence=5)

        database.insert_event(packet)

        database.update_event_artifacts(
            packet,
            image_filename="updated.jpg",
            ai_analysis="Possible tampering detected"
        )

        event = database.get_latest_events()[0]

        self.assertEqual(event[7], "updated.jpg")
        self.assertEqual(
            event[8],
            "Possible tampering detected"
        )

    def test_record_seen(self):
        packet = self.make_packet(sequence=15)

        database.record_seen(packet)

        conn = sqlite3.connect(self.test_db)

        try:
            result = conn.execute(
                "SELECT seal_id, last_event_sequence "
                "FROM seal_status WHERE seal_id = 1"
            ).fetchone()

            self.assertEqual(result, (1, 15))

        finally:
            conn.close()

    def test_record_seen_updates_sequence(self):
        database.record_seen(self.make_packet(sequence=1))
        database.record_seen(self.make_packet(sequence=2))

        conn = sqlite3.connect(self.test_db)

        try:
            result = conn.execute(
                "SELECT last_event_sequence "
                "FROM seal_status WHERE seal_id = 1"
            ).fetchone()

            self.assertEqual(result[0], 2)

        finally:
            conn.close()

    def test_stale_seal_detection(self):
        packet = self.make_packet()

        database.record_seen(packet)

        # Simulate a seal that has not communicated for 1 hour.
        conn = sqlite3.connect(self.test_db)

        try:
            conn.execute(
                "UPDATE seal_status "
                "SET last_seen = datetime('now', '-1 hour') "
                "WHERE seal_id = 1"
            )
            conn.commit()

        finally:
            conn.close()

        stale_seals = database.get_stale_seals(
            timeout_seconds=300
        )

        self.assertEqual(len(stale_seals), 1)
        self.assertEqual(stale_seals[0][0], 1)

    def test_recent_seal_not_stale(self):
        database.record_seen(self.make_packet())

        stale_seals = database.get_stale_seals(
            timeout_seconds=300
        )

        self.assertEqual(stale_seals, [])

    def test_clear_event_history(self):
        packet = self.make_packet()

        database.insert_event(packet)
        database.record_seen(packet)

        database.clear_event_history()

        events = database.get_latest_events()

        self.assertEqual(events, [])

        conn = sqlite3.connect(self.test_db)

        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM seal_status"
            ).fetchone()[0]

            self.assertEqual(count, 0)

        finally:
            conn.close()

    def test_archive_events(self):
        database.insert_event(
            self.make_packet(sequence=1)
        )

        database.insert_event(
            self.make_packet(sequence=2)
        )

        archive_path = database.archive_events()

        self.assertTrue(archive_path.exists())

        with archive_path.open(
            "r",
            newline="",
            encoding="utf-8"
        ) as file:
            rows = list(csv.reader(file))

        # Header + two stored events.
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][3], "event_sequence")


if __name__ == "__main__":
    unittest.main()