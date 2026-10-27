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
        self.addCleanup(self.temp_dir.cleanup)

        self.test_db = Path(self.temp_dir.name) / "test_smartseal.db"

        # Redirect database operations to the temporary database.
        db_patch = patch.object(database, "DB_NAME", self.test_db)
        db_patch.start()
        self.addCleanup(db_patch.stop)

        database.init_database()

    def make_packet(self):
        return {
            "seal_id": 1,
            "temperature": 5.5,
            "tamper": False,
            "vibration": True
        }

    def test_database_creation(self):
        self.assertTrue(self.test_db.exists())

    def test_events_table_exists(self):
        # Explicitly close the SQLite connection to avoid Windows file locks.
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
        database.insert_event(self.make_packet())

        events = database.get_latest_events()

        self.assertEqual(len(events), 1)

    def test_sensor_values(self):
        database.insert_event(self.make_packet())

        event = database.get_latest_events()[0]

        self.assertEqual(event[2], 1)       # seal_id
        self.assertEqual(event[3], 5.5)     # temperature
        self.assertEqual(event[4], 0)       # tamper
        self.assertEqual(event[5], 1)       # vibration

    def test_image_and_ai_analysis(self):
        database.insert_event(
            self.make_packet(),
            image_filename="test_image.jpg",
            ai_analysis="No visible damage"
        )

        event = database.get_latest_events()[0]

        self.assertEqual(event[6], "test_image.jpg")
        self.assertEqual(event[7], "No visible damage")

    def test_event_limit(self):
        for i in range(5):
            packet = self.make_packet()
            packet["temperature"] = 3.0 + i
            database.insert_event(packet)

        events = database.get_latest_events(limit=3)

        self.assertEqual(len(events), 3)

    def test_empty_database(self):
        events = database.get_latest_events()

        self.assertEqual(events, [])

    def test_database_initialization_twice(self):
        database.init_database()
        database.init_database()

        self.assertTrue(self.test_db.exists())


if __name__ == "__main__":
    unittest.main()