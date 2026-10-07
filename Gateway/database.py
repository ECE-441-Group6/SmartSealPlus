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
        temperature REAL,
        tamper INTEGER,
        vibration INTEGER,
        image_path TEXT,
        ai_analysis TEXT
    )
    """)

    # Add newer columns when opening a database created by an older version.
    for column in ("image_path", "ai_analysis"):
        try:
            cur.execute(f"ALTER TABLE events ADD COLUMN {column} TEXT")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def insert_event(packet, image_filename=None, ai_analysis=None):
    # Store one normalized gateway packet and any evidence generated for it.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO events
    (seal_id, temperature, tamper, vibration, image_path, ai_analysis)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (
        packet["seal_id"],
        packet["temperature"],
        int(packet["tamper"]),
        int(packet["vibration"]),
        image_filename,
        ai_analysis
    ))

    conn.commit()
    conn.close()


def get_latest_events(limit=20):
    # Return the newest events first for the dashboard and its JSON endpoint.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM events
    ORDER BY timestamp DESC
    LIMIT ?
    """, (limit,))

    rows = cur.fetchall()

    conn.close()

    return rows