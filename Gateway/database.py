# Saves sensor readings and events so they can be reviewed later.
import csv
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

DB_NAME = Path(__file__).resolve().parent / "smartseal.db"
IMAGE_FOLDER = DB_NAME.parent / "images"
ARCHIVE_DIRECTORY = DB_NAME.parent / "archives"


def _delete_unreferenced_images():
    referenced = set()
    conn = sqlite3.connect(DB_NAME)
    try:
        referenced.update(
            row[0] for row in conn.execute(
                "SELECT image_path FROM events "
                "WHERE image_path IS NOT NULL AND image_path != ''"
            )
        )
    finally:
        conn.close()

    for archive_path in ARCHIVE_DIRECTORY.glob("*.csv"):
        try:
            with archive_path.open(newline="", encoding="utf-8") as archive_file:
                referenced.update(
                    (row.get("image_path") or "").strip()
                    for row in csv.DictReader(archive_file)
                    if (row.get("image_path") or "").strip()
                )
        except (OSError, csv.Error):
            continue

    image_folder = IMAGE_FOLDER.resolve()
    for image_path in IMAGE_FOLDER.glob("*"):
        if image_path.name not in referenced and image_path.is_file():
            resolved = image_path.resolve()
            if resolved.parent == image_folder:
                resolved.unlink()


def apply_retention_policy():
    cutoff = (datetime.utcnow() - timedelta(days=30)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute(
            """
            DELETE FROM events
            WHERE timestamp < ?
              AND COALESCE(image_path, '') = ''
              AND COALESCE(ai_analysis, '') = ''
            """,
            (cutoff,),
        )
        conn.commit()
    finally:
        conn.close()

    ARCHIVE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    archive_cutoff = datetime.now().timestamp() - timedelta(days=90).total_seconds()
    for archive_path in ARCHIVE_DIRECTORY.glob("*.csv"):
        if archive_path.stat().st_mtime >= archive_cutoff:
            continue
        try:
            with archive_path.open(newline="", encoding="utf-8") as archive_file:
                rows = list(csv.DictReader(archive_file))
        except (OSError, csv.Error):
            continue
        if any(
            (row.get("image_path") or "").strip()
            or (row.get("ai_analysis") or "").strip()
            for row in rows
        ):
            continue
        archive_path.unlink()

    _delete_unreferenced_images()


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
        movement_type INTEGER DEFAULT 0,
        image_path TEXT,
        ai_analysis TEXT
    )
    """)

    # Add newer columns when opening a database created by an older version.
    for column in ("event_sequence", "movement_type", "image_path", "ai_analysis"):
        try:
            column_type = (
                "INTEGER"
                if column in ("event_sequence", "movement_type")
                else "TEXT"
            )
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
    apply_retention_policy()


def clear_event_history():
    conn = sqlite3.connect(DB_NAME)
    with conn:
        conn.execute(
            """
            DELETE FROM events
            WHERE COALESCE(image_path, '') = ''
              AND COALESCE(ai_analysis, '') = ''
            """
        )
        conn.execute("DELETE FROM seal_status")
    conn.close()
    _delete_unreferenced_images()


def insert_event(packet, image_filename=None, ai_analysis=None):
    # Store one normalized gateway packet and any evidence generated for it.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO events
    (seal_id, event_sequence, temperature, tamper, vibration, movement_type,
     image_path, ai_analysis)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        packet["seal_id"],
        packet["event_sequence"],
        packet["temperature"],
        int(packet["tamper"]),
        packet["vibration"],
        packet.get("movement_type", 0),
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

def get_stale_seals(timeout_seconds):
    conn = sqlite3.connect(DB_NAME)
    rows = conn.execute("""
    SELECT seal_id, last_seen
    FROM seal_status
    WHERE (julianday('now') - julianday(last_seen)) * 86400 > ?
    """, (timeout_seconds,)).fetchall()
    conn.close()
    return rows


def get_latest_events():
    # Return the complete event history, newest first, for the dashboard.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    SELECT id, timestamp, seal_id, event_sequence, temperature, tamper,
           vibration, movement_type, image_path, ai_analysis
    FROM events
    ORDER BY timestamp DESC, id DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


def archive_events():
    conn = sqlite3.connect(DB_NAME)
    try:
        rows = conn.execute("""
        SELECT id, timestamp, seal_id, event_sequence, temperature, tamper,
               vibration, movement_type, image_path, ai_analysis
        FROM events
        ORDER BY timestamp ASC, id ASC
        """).fetchall()
    finally:
        conn.close()

    if not rows:
        return None

    archive_dir = DB_NAME.parent / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / (
        f"SmartSeal_Events_{datetime.now().strftime('%m-%d-%y_%I-%M-%S-%p')}.csv"
    )

    with archive_path.open("w", newline="", encoding="utf-8") as archive_file:
        writer = csv.writer(archive_file)
        writer.writerow((
            "id",
            "timestamp",
            "seal_id",
            "event_sequence",
            "temperature",
            "tamper",
            "vibration",
            "movement_type",
            "image_path",
            "ai_analysis",
        ))
        writer.writerows(rows)

    return archive_path