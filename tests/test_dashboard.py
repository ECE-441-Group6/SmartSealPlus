import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Gateway import database
from Dashboard import dashboard


class TestDashboardIntegration(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite database for each test.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.test_db = Path(self.temp_dir.name) / "test_dashboard.db"

        # Redirect Gateway.database to the temporary database.
        db_patch = patch.object(database, "DB_NAME", self.test_db)
        db_patch.start()
        self.addCleanup(db_patch.stop)

        # The dashboard imports database using a different module name.
        # Redirect the database used by the dashboard as well.
        dashboard_db_patch = patch.dict(
            dashboard.get_latest_events.__globals__,
            {"DB_NAME": self.test_db}
        )
        dashboard_db_patch.start()
        self.addCleanup(dashboard_db_patch.stop)

        # Initialize the temporary database.
        database.init_database()

        # Configure Flask for testing.
        dashboard.app.config["TESTING"] = True

        # Create a Flask test client.
        # No web server needs to be started.
        self.client = dashboard.app.test_client()

    def make_packet(self, temperature=5.0, tamper=False, vibration=False):
        return {
            "seal_id": 1,
            "temperature": temperature,
            "tamper": tamper,
            "vibration": vibration
        }

    def test_home_page(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<html", response.data.lower())

    def test_empty_events_api(self):
        response = self.client.get("/api/events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_api_returns_stored_event(self):
        database.insert_event(
            self.make_packet(temperature=5.5)
        )

        response = self.client.get("/api/events")

        self.assertEqual(response.status_code, 200)

        events = response.get_json()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][2], 1)
        self.assertEqual(events[0][3], 5.5)

    def test_api_returns_tamper_and_vibration(self):
        database.insert_event(
            self.make_packet(
                temperature=6.0,
                tamper=True,
                vibration=True
            )
        )

        response = self.client.get("/api/events")

        self.assertEqual(response.status_code, 200)

        events = response.get_json()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][4], 1)
        self.assertEqual(events[0][5], 1)

    def test_api_returns_multiple_events(self):
        database.insert_event(
            self.make_packet(temperature=4.0)
        )

        database.insert_event(
            self.make_packet(temperature=7.0)
        )

        response = self.client.get("/api/events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 2)

    def test_api_returns_image_and_analysis(self):
        database.insert_event(
            self.make_packet(),
            image_filename="evidence.jpg",
            ai_analysis="Possible damage detected"
        )

        response = self.client.get("/api/events")

        self.assertEqual(response.status_code, 200)

        events = response.get_json()

        self.assertEqual(len(events), 1)

        event = events[0]

        self.assertEqual(event[6], "evidence.jpg")
        self.assertEqual(event[7], "Possible damage detected")

    def test_unknown_route(self):
        response = self.client.get("/nonexistent")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()