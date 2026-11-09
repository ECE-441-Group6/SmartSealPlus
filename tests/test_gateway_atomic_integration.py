
"""Integration tests for atomic storage in the SmartSeal+ gateway."""

import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from Gateway import database, gateway_main


class TestGatewayAtomicIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

        self.db_path = Path(self.temp_directory.name) / "gateway_test.db"

        db_patch = patch.object(database, "DB_NAME", self.db_path)
        db_patch.start()
        self.addCleanup(db_patch.stop)

        database.init_database()

    @staticmethod
    def packet(sequence=101):
        return {
            "seal_id": 1,
            "event_sequence": sequence,
            "temperature": 5.0,
            "tamper": True,
            "vibration": 0.0,
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
            return conn.execute(
                "SELECT COUNT(*) FROM events"
            ).fetchone()[0]

    def test_database_failure_then_successful_retry(self):
        packet = self.packet()
        scan_count = 0

        # First insertion fails; a later scan retries the same packet.
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute("""
                    CREATE TRIGGER block_event
                    BEFORE INSERT ON events
                    BEGIN
                        SELECT RAISE(
                            ABORT,
                            'simulated database failure'
                        );
                    END;
                """)

        def scanner():
            nonlocal scan_count
            scan_count += 1

            if scan_count == 1:
                return packet.copy()

            if scan_count == 2:
                # Database recovers before retransmission.
                with closing(sqlite3.connect(self.db_path)) as conn:
                    with conn:
                        conn.execute("DROP TRIGGER block_event")

                # The first failed attempt must not advance the sequence.
                self.assertIsNone(self.last_sequence())
                self.assertEqual(self.event_count(), 0)

                return packet.copy()

            if scan_count == 3:
                # Duplicate retransmission after successful storage.
                return packet.copy()

            raise KeyboardInterrupt

        with (
            patch.object(
                gateway_main,
                "load_key_registry",
                return_value=None,
            ),
            patch.object(
                gateway_main,
                "process_alerts",
                return_value=["TAMPER ALERT"],
            ) as alerts,
            patch.object(
                gateway_main,
                "capture_image",
                return_value=None,
            ) as camera,
            patch.object(
                gateway_main.time,
                "sleep",
                return_value=None,
            ),
            redirect_stdout(io.StringIO()) as output,
        ):
            gateway_main.run_gateway(
                interval=0,
                scanner=scanner,
            )

        # Only the successfully stored event triggers side effects.
        self.assertEqual(self.event_count(), 1)
        self.assertEqual(self.last_sequence(), 101)
        self.assertEqual(alerts.call_count, 1)
        self.assertEqual(camera.call_count, 1)

        logs = output.getvalue()
        self.assertIn(
            "Rejected packet: database transaction failed",
            logs,
        )
        self.assertIn("Event recorded: seal=1 seq=101", logs)
        self.assertIn(
            "Rejected packet: duplicate event",
            logs,
        )


if __name__ == "__main__":
    unittest.main()
