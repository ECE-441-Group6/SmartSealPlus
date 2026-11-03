"""Sequence validation utilities for SmartSeal+ sensor events."""

import sqlite3
from contextlib import closing
from pathlib import Path

MAX_SEQUENCE = 0xFFFFFFFF


class ReplayProtector:
    """Track event sequences independently for each seal."""

    def __init__(self, db_path=None):
        self.last_sequences = {}
        self.db_path = Path(db_path) if db_path is not None else None

        if self.db_path is not None:
            self._initialize_database()

    def _initialize_database(self):
        """Create a dedicated table for persistent replay protection."""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn, conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS security_sequences (
                    seal_id INTEGER PRIMARY KEY,
                    last_sequence INTEGER NOT NULL
                )
            """)

    def check_sequence(self, seal_id, sequence):
        """Accept only sequences newer than the last accepted sequence."""

        if (
            type(seal_id) is not int
            or not 0 < seal_id <= MAX_SEQUENCE
        ):
            return False, "invalid seal ID"

        if (
            type(sequence) is not int
            or not 0 <= sequence <= MAX_SEQUENCE
        ):
            return False, "invalid event sequence"

        if self.db_path is None:
            previous = self.last_sequences.get(seal_id)

            if previous is not None:
                if sequence == previous:
                    return False, "duplicate event"

                if sequence < previous:
                    return False, "outdated event sequence"

            self.last_sequences[seal_id] = sequence
            return True, "accepted"

        try:
            with closing(sqlite3.connect(self.db_path, timeout=10)) as conn, conn:
                conn.execute("BEGIN IMMEDIATE")

                row = conn.execute(
                    """
                    SELECT last_sequence
                    FROM security_sequences
                    WHERE seal_id = ?
                    """,
                    (seal_id,),
                ).fetchone()

                if row is not None:
                    previous = row[0]

                    if sequence == previous:
                        return False, "duplicate event"

                    if sequence < previous:
                        return False, "outdated event sequence"

                conn.execute(
                    """
                    INSERT INTO security_sequences (seal_id, last_sequence)
                    VALUES (?, ?)
                    ON CONFLICT(seal_id) DO UPDATE SET
                        last_sequence = excluded.last_sequence
                    """,
                    (seal_id, sequence),
                )

            self.last_sequences[seal_id] = sequence
            return True, "accepted"

        except sqlite3.Error:
            return False, "security database unavailable"
