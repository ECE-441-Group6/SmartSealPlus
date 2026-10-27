# Saves sensor readings and events so they can be reviewed later.
from pathlib import Path
import sqlite3

DB_NAME = Path(__file__).resolve().parent / "smartseal.db"


def init_database():
    # Create the local SQLite database and its event table if they do not exist.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        seal_id INTEGER,
        event_sequence INTEGER,
        temperature REAL,
        tamper INTEGER,
        vibration REAL,
        image_path TEXT,
        ai_analysis TEXT
    )
    """)

    # Add newer columns when opening a database created by an older version.
    for column in ("event_sequence", "image_path", "ai_analysis"):
        try:
            column_type = "INTEGER" if column == "event_sequence" else "TEXT"
            cur.execute(f"ALTER TABLE events ADD COLUMN {column} {column_type}")
        except sqlite3.OperationalError:
            pass

    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_events_seal_sequence
    ON events(seal_id, event_sequence)
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS seal_status(
        seal_id INTEGER PRIMARY KEY,
        last_seen DATETIME NOT NULL,
        last_event_sequence INTEGER,
        last_delivery_failure DATETIME
    )
    """)

    conn.commit()
    conn.close()


def insert_event(packet, image_filename=None, ai_analysis=None):
    # Store one normalized gateway packet and any evidence generated for it.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO events
    (seal_id, event_sequence, temperature, tamper, vibration, image_path, ai_analysis)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    (
        packet["seal_id"],
        packet["event_sequence"],
        packet["temperature"],
        int(packet["tamper"]),
        packet["vibration"],
        image_filename,
        ai_analysis
    ))

    inserted = cur.rowcount == 1
    conn.commit()
    conn.close()
    return inserted


def update_event_artifacts(packet, image_filename=None, ai_analysis=None):
    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        """
        UPDATE events
        SET image_path = ?, ai_analysis = ?
        WHERE seal_id = ? AND event_sequence = ?
        """,
        (
            image_filename,
            ai_analysis,
            packet["seal_id"],
            packet["event_sequence"],
        ),
    )
    conn.commit()
    conn.close()


def record_seen(packet):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
    INSERT INTO seal_status(seal_id, last_seen, last_event_sequence)
    VALUES (?, CURRENT_TIMESTAMP, ?)
    ON CONFLICT(seal_id) DO UPDATE SET
        last_seen = excluded.last_seen,
        last_event_sequence = excluded.last_event_sequence
    """, (packet["seal_id"], packet["event_sequence"]))
    conn.commit()
    conn.close()


def is_stale_sequence(packet):
    conn = sqlite3.connect(DB_NAME)
    row = conn.execute(
        "SELECT last_event_sequence FROM seal_status WHERE seal_id = ?",
        (packet["seal_id"],),
    ).fetchone()
    existing = conn.execute(
        "SELECT 1 FROM events WHERE seal_id = ? AND event_sequence = ?",
        (packet["seal_id"], packet["event_sequence"]),
    ).fetchone()
    conn.close()
    if existing is not None:
        return True
    if row is None or row[0] is None:
        return False
    previous = int(row[0])
    current = packet["event_sequence"]
    distance = (current - previous) & 0xFFFFFFFF
    return (
        current != previous
        and distance > 0x7FFFFFFF
        and current > previous
    )


def get_stale_seals(timeout_seconds):
    conn = sqlite3.connect(DB_NAME)
    rows = conn.execute("""
    SELECT seal_id, last_seen
    FROM seal_status
    WHERE (julianday('now') - julianday(last_seen)) * 86400 > ?
    """, (timeout_seconds,)).fetchall()
    conn.close()
    return rows


def get_latest_events(limit=20):
    # Return the newest events first for the dashboard and its JSON endpoint.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    SELECT id, timestamp, seal_id, event_sequence, temperature, tamper,
           vibration, image_path, ai_analysis
    FROM events
    ORDER BY timestamp DESC
    LIMIT ?
    """, (limit,))

    rows = cur.fetchall()

    conn.close()

    return rows