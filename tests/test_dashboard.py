import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Gateway import database
from Dashboard import dashboard


class TestDashboardIntegration(unittest.TestCase):

    def setUp(self):
        # Create isolated temporary storage for every test.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.test_dir = Path(self.temp_dir.name)
        self.test_db = self.test_dir / "test_dashboard.db"
        self.archive_dir = self.test_dir / "archives"
        self.archive_dir.mkdir()

        # Redirect database operations to temporary storage.
        db_patch = patch.object(database, "DB_NAME", self.test_db)
        db_patch.start()
        self.addCleanup(db_patch.stop)

        # Redirect archive operations to temporary storage.
        archive_patch = patch.object(
            dashboard,
            "ARCHIVE_DIRECTORY",
            self.archive_dir
        )
        archive_patch.start()
        self.addCleanup(archive_patch.stop)

        database.init_database()

        # Configure Flask for testing.
        dashboard.app.config["TESTING"] = True
        self.client = dashboard.app.test_client()

    def make_packet(
        self,
        temperature=5.0,
        tamper=False,
        vibration=0.5,
        sequence=1,
        seal_id=1
    ):
        return {
            "seal_id": seal_id,
            "event_sequence": sequence,
            "temperature": temperature,
            "tamper": tamper,
            "vibration": vibration
        }

    def make_archive(self, filename=None):
        if filename is None:
            filename = "gateway-events-20261029-120000-123456.csv"

        archive_path = self.archive_dir / filename

        with archive_path.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as file:
            writer = csv.writer(file)

            writer.writerow([
                "id",
                "timestamp",
                "seal_id",
                "event_sequence",
                "temperature",
                "tamper",
                "vibration",
                "image_path",
                "ai_analysis"
            ])

            writer.writerow([
                1,
                "2026-10-29 12:00:00",
                1,
                10,
                5.5,
                0,
                0.5,
                "evidence.jpg",
                "No visible damage"
            ])

        return archive_path

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
        self.assertEqual(events[0][3], 1)
        self.assertEqual(events[0][4], 5.5)

    def test_api_returns_tamper_and_vibration(self):
        database.insert_event(
            self.make_packet(
                temperature=6.0,
                tamper=True,
                vibration=1.25
            )
        )

        response = self.client.get("/api/events")

        self.assertEqual(response.status_code, 200)

        events = response.get_json()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][5], 1)
        self.assertEqual(events[0][6], 1.25)

    def test_api_returns_multiple_events(self):
        database.insert_event(
            self.make_packet(
                temperature=4.0,
                sequence=1
            )
        )

        database.insert_event(
            self.make_packet(
                temperature=7.0,
                sequence=2
            )
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

        self.assertEqual(event[7], "evidence.jpg")
        self.assertEqual(event[8], "Possible damage detected")

    def test_unknown_route(self):
        response = self.client.get("/nonexistent")

        self.assertEqual(response.status_code, 404)

    def test_events_api_cache_control(self):
        response = self.client.get("/api/events")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "no-store",
            response.headers.get("Cache-Control", "")
        )

    def test_home_page_cache_control(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "no-store",
            response.headers.get("Cache-Control", "")
        )

    def test_empty_archives_api(self):
        response = self.client.get("/api/archives")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_archives_api_lists_valid_archives(self):
        archive_path = self.make_archive()

        response = self.client.get("/api/archives")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            [archive_path.name]
        )

    def test_archives_api_ignores_invalid_files(self):
        self.make_archive()

        invalid_file = self.archive_dir / "private.txt"
        invalid_file.write_text(
            "Sensitive information",
            encoding="utf-8"
        )

        response = self.client.get("/api/archives")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 1)

    def test_archive_events_api(self):
        archive_path = self.make_archive()

        response = self.client.get(
            f"/api/archives/{archive_path.name}"
        )

        self.assertEqual(response.status_code, 200)

        events = response.get_json()

        self.assertEqual(len(events), 1)

        event = events[0]

        self.assertEqual(event[2], 1)
        self.assertEqual(event[3], 10)
        self.assertEqual(event[4], 5.5)
        self.assertEqual(event[5], 0)
        self.assertEqual(event[6], 0.5)
        self.assertEqual(event[7], "evidence.jpg")
        self.assertEqual(event[8], "No visible damage")

    def test_archive_not_found(self):
        response = self.client.get(
            "/api/archives/gateway-events-20261029-120000-999999.csv"
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_archive_filename(self):
        response = self.client.get(
            "/api/archives/private.txt"
        )

        self.assertEqual(response.status_code, 404)

    def test_archive_path_traversal_rejected(self):
        # Test the filename validator directly.
        self.assertIsNone(
            dashboard._archive_path("../private.txt")
        )

        self.assertIsNone(
            dashboard._archive_path("../../secret.csv")
        )

    def test_archives_api_cache_control(self):
        response = self.client.get("/api/archives")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "no-store",
            response.headers.get("Cache-Control", "")
        )


if __name__ == "__main__":
    unittest.main()