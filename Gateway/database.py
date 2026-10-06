# Saves sensor readings and events so they can be reviewed later. SQLite would be a good option.
import sqlite3

DB_NAME = "smartseal.db"


def init_database():

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        seal_id INTEGER,
        temperature REAL,
        tamper INTEGER,
        vibration INTEGER
    )
    """)

    conn.commit()
    conn.close()


def insert_event(packet):

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO events
    (seal_id, temperature, tamper, vibration)
    VALUES (?, ?, ?, ?)
    """,
    (
        packet["seal_id"],
        packet["temperature"],
        int(packet["tamper"]),
        int(packet["vibration"])
    ))

    conn.commit()
    conn.close()


def get_latest_events(limit=20):

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